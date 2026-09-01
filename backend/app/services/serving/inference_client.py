import httpx

from app.core.config import settings


class InferenceClient:
    def __init__(self, base_url: str | None = None, timeout: float = 180.0):
        self.base_url = (base_url or settings.inference_url).rstrip("/")
        self.timeout = timeout

    async def load_model(
        self,
        model_name: str,
        artifact_path: str,
        traffic_pct: float,
        deployed_model_id: int,
    ) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/admin/models/load",
                json={
                    "model_name": model_name,
                    "artifact_path": artifact_path,
                    "traffic_pct": traffic_pct,
                    "deployed_model_id": deployed_model_id,
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def set_route(self, model_name: str, traffic_pct: float) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.base_url}/admin/routes",
                json={"model_name": model_name, "traffic_pct": traffic_pct},
            )
            resp.raise_for_status()
            return resp.json()
