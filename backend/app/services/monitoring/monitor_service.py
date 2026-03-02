from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import HumanRating, InferenceLog


class MonitorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_metrics_summary(self, hours: int = 24) -> dict:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.db.execute(
            select(
                func.avg(InferenceLog.latency_ms).label("avg_latency"),
                func.percentile_cont(0.95).within_group(InferenceLog.latency_ms).label("p95"),
                func.percentile_cont(0.99).within_group(InferenceLog.latency_ms).label("p99"),
                func.count(InferenceLog.id).label("total"),
                func.sum(InferenceLog.tokens_out).label("total_tokens_out"),
            ).where(InferenceLog.created_at >= since)
        )
        row = result.one_or_none()

        total = row.total if row and row.total else 0
        total_tokens = row.total_tokens_out if row and row.total_tokens_out else 0
        elapsed_seconds = hours * 3600

        return {
            "avg_latency_ms": round(row.avg_latency, 2) if row and row.avg_latency else 0.0,
            "p95_latency_ms": round(row.p95, 2) if row and row.p95 else 0.0,
            "p99_latency_ms": round(row.p99, 2) if row and row.p99 else 0.0,
            "total_requests": total,
            "error_rate": 0.0,
            "tokens_per_second": round(total_tokens / elapsed_seconds, 2) if elapsed_seconds > 0 else 0.0,
        }

    async def get_quality_metrics(self, days: int = 30) -> dict:
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(
                func.avg(HumanRating.score).label("avg_score"),
                func.count(HumanRating.id).label("total"),
            ).where(HumanRating.created_at >= since)
        )
        row = result.one_or_none()

        dim_result = await self.db.execute(
            select(
                HumanRating.dimension,
                func.avg(HumanRating.score).label("avg"),
            )
            .where(HumanRating.created_at >= since)
            .group_by(HumanRating.dimension)
        )
        score_by_dim = {r.dimension: round(r.avg, 2) for r in dim_result.all()}

        return {
            "avg_human_score": round(row.avg_score, 2) if row and row.avg_score else 0.0,
            "total_ratings": row.total if row and row.total else 0,
            "score_by_dimension": score_by_dim,
        }
