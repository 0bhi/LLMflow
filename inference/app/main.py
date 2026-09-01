import hashlib
import time
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response

from app.core.config import settings
from app.engine.batcher import RequestBatcher
from app.engine.cache import ResponseCache
from app.models.loader import ModelManager
from app.router.ab_router import ABRouter

logger = structlog.get_logger()

REQUEST_COUNT = Counter("inference_requests_total", "Total inference requests", ["model"])
REQUEST_LATENCY = Histogram(
    "inference_request_latency_ms",
    "Inference latency in ms",
    ["model"],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
)
TOKENS_GENERATED = Counter("inference_tokens_generated_total", "Total tokens generated", ["model"])

model_manager = ModelManager()
batcher = RequestBatcher(model_manager)
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


class LoadModelRequest(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_name: str
    artifact_path: str
    traffic_pct: float = Field(100.0, ge=0.0, le=100.0)
    deployed_model_id: int | None = None


class RouteRequest(BaseModel):
    model_name: str
    traffic_pct: float = Field(..., ge=0.0, le=100.0)


async def _log_completion(
    *,
    model_name: str,
    prompt: str,
    completion: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: float,
    deployed_model_id: int | None,
) -> None:
    if not settings.backend_url:
        return
    payload = {
        "model_name": model_name,
        "prompt": prompt,
        "completion": completion,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "deployed_model_id": deployed_model_id,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.backend_url.rstrip('/')}/api/v1/serving/inference-logs",
                json=payload,
            )
    except Exception as exc:
        logger.warning("inference_log_failed", error=str(exc))


@app.post("/v1/completions", response_model=InferenceResponse)
async def create_completion(request: InferenceRequest):
    model_name = ab_router.route(request.model)

    prompt_hash = hashlib.sha256(
        f"{model_name}:{request.prompt}:{request.max_tokens}:{request.temperature}".encode()
    ).hexdigest()

    cached_response = await cache.get(prompt_hash)
    if cached_response and "not loaded. This is a placeholder" not in str(
        cached_response.get("completion", "")
    ):
        REQUEST_COUNT.labels(model=model_name).inc()
        await _log_completion(
            model_name=model_name,
            prompt=request.prompt,
            completion=cached_response["completion"],
            tokens_in=cached_response["tokens_in"],
            tokens_out=cached_response["tokens_out"],
            latency_ms=cached_response.get("latency_ms", 0),
            deployed_model_id=cached_response.get("deployed_model_id"),
        )
        return InferenceResponse(
            **{k: v for k, v in cached_response.items() if k != "deployed_model_id"},
            cached=True,
        )
    if cached_response:
        await cache.invalidate(prompt_hash)

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
        "deployed_model_id": result.get("deployed_model_id"),
    }

    if not result.get("placeholder"):
        await cache.set(prompt_hash, response_data, ttl=3600)
    await _log_completion(
        model_name=model_name,
        prompt=request.prompt,
        completion=result["completion"],
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
        latency_ms=round(latency_ms, 2),
        deployed_model_id=result.get("deployed_model_id"),
    )

    return InferenceResponse(
        completion=response_data["completion"],
        model=model_name,
        tokens_in=response_data["tokens_in"],
        tokens_out=response_data["tokens_out"],
        latency_ms=response_data["latency_ms"],
    )


@app.post("/admin/models/load")
async def load_model(payload: LoadModelRequest):
    try:
        await model_manager.load_model(
            model_name=payload.model_name,
            model_path=payload.artifact_path,
            deployed_model_id=payload.deployed_model_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"Failed to load model: {e}") from e
    ab_router.set_route(payload.model_name, payload.traffic_pct)
    return {
        "status": "loaded",
        "model_name": payload.model_name,
        "traffic_pct": payload.traffic_pct,
        "models_loaded": model_manager.list_loaded(),
    }


@app.post("/admin/routes")
async def set_route(payload: RouteRequest):
    ab_router.set_route(payload.model_name, payload.traffic_pct)
    return {"model_name": payload.model_name, "traffic_pct": payload.traffic_pct}


@app.get("/admin/models")
async def list_models():
    return {
        "loaded": model_manager.list_loaded(),
        "routes": ab_router.list_models(),
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "models_loaded": model_manager.list_loaded()}


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type="text/plain")
