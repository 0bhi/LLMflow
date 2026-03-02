import hashlib
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response

from app.engine.batcher import RequestBatcher
from app.engine.cache import ResponseCache
from app.router.ab_router import ABRouter

REQUEST_COUNT = Counter("inference_requests_total", "Total inference requests", ["model"])
REQUEST_LATENCY = Histogram(
    "inference_request_latency_ms", "Inference latency in ms", ["model"],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
)
TOKENS_GENERATED = Counter("inference_tokens_generated_total", "Total tokens generated", ["model"])

batcher = RequestBatcher()
cache = ResponseCache()
ab_router = ABRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await cache.connect()
    yield
    await cache.close()


app = FastAPI(title="LLMflow Inference Server", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class InferenceRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_tokens: int = Field(256, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    model: str | None = None
    stream: bool = False


class InferenceResponse(BaseModel):
    completion: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cached: bool = False


@app.post("/v1/completions", response_model=InferenceResponse)
async def create_completion(request: InferenceRequest):
    model_name = ab_router.route(request.model)

    prompt_hash = hashlib.sha256(
        f"{model_name}:{request.prompt}:{request.max_tokens}:{request.temperature}".encode()
    ).hexdigest()

    cached_response = await cache.get(prompt_hash)
    if cached_response:
        REQUEST_COUNT.labels(model=model_name).inc()
        return InferenceResponse(**cached_response, cached=True)

    start = time.perf_counter()
    result = await batcher.process(
        model_name=model_name,
        prompt=request.prompt,
        max_tokens=request.max_tokens,
        temperature=request.temperature,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    REQUEST_COUNT.labels(model=model_name).inc()
    REQUEST_LATENCY.labels(model=model_name).observe(latency_ms)
    TOKENS_GENERATED.labels(model=model_name).inc(result["tokens_out"])

    response_data = {
        "completion": result["completion"],
        "model": model_name,
        "tokens_in": result["tokens_in"],
        "tokens_out": result["tokens_out"],
        "latency_ms": round(latency_ms, 2),
    }

    await cache.set(prompt_hash, response_data, ttl=3600)

    return InferenceResponse(**response_data)


@app.get("/health")
async def health():
    return {"status": "healthy", "models_loaded": ab_router.list_models()}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
