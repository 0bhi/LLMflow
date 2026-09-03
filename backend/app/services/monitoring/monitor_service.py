from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inference import HumanRating, InferenceLog

PLACEHOLDER_SNIPPET = "not loaded. This is a placeholder"


class MonitorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_metrics_summary(self, hours: int = 24) -> dict:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        dialect = self.db.bind.dialect.name if self.db.bind else "postgresql"

        if dialect == "postgresql":
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
            p95 = round(row.p95, 2) if row and row.p95 else 0.0
            p99 = round(row.p99, 2) if row and row.p99 else 0.0
        else:
            result = await self.db.execute(
                select(
                    func.avg(InferenceLog.latency_ms).label("avg_latency"),
                    func.count(InferenceLog.id).label("total"),
                    func.sum(InferenceLog.tokens_out).label("total_tokens_out"),
                ).where(InferenceLog.created_at >= since)
            )
            row = result.one_or_none()
            p95 = p99 = round(row.avg_latency, 2) if row and row.avg_latency else 0.0

        total = row.total if row and row.total else 0
        total_tokens = row.total_tokens_out if row and row.total_tokens_out else 0
        elapsed_seconds = hours * 3600

        error_result = await self.db.execute(
            select(func.count(InferenceLog.id)).where(
                InferenceLog.created_at >= since,
                InferenceLog.completion.contains(PLACEHOLDER_SNIPPET),
            )
        )
        error_count = error_result.scalar() or 0
        error_rate = round((error_count / total) * 100, 2) if total else 0.0

        return {
            "avg_latency_ms": round(row.avg_latency, 2) if row and row.avg_latency else 0.0,
            "p95_latency_ms": p95,
            "p99_latency_ms": p99,
            "total_requests": total,
            "error_rate": error_rate,
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

        series_result = await self.db.execute(
            select(HumanRating.created_at, HumanRating.score).where(HumanRating.created_at >= since)
        )
        buckets: dict[str, list[float]] = {}
        for created_at, score in series_result.all():
            if created_at is None:
                continue
            day = created_at.date().isoformat() if hasattr(created_at, "date") else str(created_at)[:10]
            buckets.setdefault(day, []).append(score)
        score_over_time = [
            {"date": day, "avg_score": round(sum(vals) / len(vals), 2)}
            for day, vals in sorted(buckets.items())
        ]

        return {
            "avg_human_score": round(row.avg_score, 2) if row and row.avg_score else 0.0,
            "total_ratings": row.total if row and row.total else 0,
            "score_by_dimension": score_by_dim,
            "score_over_time": score_over_time,
        }
