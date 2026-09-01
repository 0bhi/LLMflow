import hashlib

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.cost import CostRecord, ResourceType
from app.models.deployment import DeployedModel, DeploymentStatus
from app.models.inference import InferenceLog
from app.schemas.serving import InferenceLogCreate


def compute_inference_cost(tokens_in: int, tokens_out: int) -> float:
    tokens = tokens_in + tokens_out
    return round((tokens / 1000.0) * settings.inference_cost_per_1k_tokens, 6)


class InferenceLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(self, payload: InferenceLogCreate) -> InferenceLog:
        deployed_model_id = payload.deployed_model_id
        if deployed_model_id is None:
            result = await self.db.execute(
                select(DeployedModel)
                .where(
                    DeployedModel.name == payload.model_name,
                    DeployedModel.status == DeploymentStatus.ACTIVE,
                )
                .order_by(DeployedModel.created_at.desc())
                .limit(1)
            )
            dep = result.scalar_one_or_none()
            if not dep:
                raise ValueError(f"No active deployment named '{payload.model_name}'")
            deployed_model_id = dep.id

        prompt_hash = hashlib.sha256(payload.prompt.encode()).hexdigest()
        cost = compute_inference_cost(payload.tokens_in, payload.tokens_out)

        log = InferenceLog(
            deployed_model_id=deployed_model_id,
            prompt_hash=prompt_hash,
            prompt=payload.prompt,
            completion=payload.completion,
            latency_ms=payload.latency_ms,
            tokens_in=payload.tokens_in,
            tokens_out=payload.tokens_out,
            cost_usd=cost,
        )
        self.db.add(log)
        await self.db.flush()

        self.db.add(
            CostRecord(
                resource_type=ResourceType.INFERENCE,
                reference_id=log.id,
                token_count=payload.tokens_in + payload.tokens_out,
                cost_usd=cost,
            )
        )
        await self.db.flush()
        return log

    async def list_recent(self, skip: int = 0, limit: int = 50) -> Sequence[InferenceLog]:
        result = await self.db.execute(
            select(InferenceLog).offset(skip).limit(limit).order_by(InferenceLog.created_at.desc())
        )
        return result.scalars().all()
