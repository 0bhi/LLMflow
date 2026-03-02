import re

from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from app.core.logging import get_logger

logger = get_logger("task_eval")


class TaskEvaluator:
    """Task-specific evaluation: classification F1 and QA exact-match."""

    def evaluate_classification(
        self, predictions: list[str], references: list[str], labels: list[str] | None = None
    ) -> dict:
        pred_normalized = [p.strip().lower() for p in predictions]
        ref_normalized = [r.strip().lower() for r in references]

        accuracy = accuracy_score(ref_normalized, pred_normalized)
        f1_macro = f1_score(ref_normalized, pred_normalized, average="macro", zero_division=0)
        f1_weighted = f1_score(
            ref_normalized, pred_normalized, average="weighted", zero_division=0
        )
        precision = precision_score(
            ref_normalized, pred_normalized, average="macro", zero_division=0
        )
        recall = recall_score(
            ref_normalized, pred_normalized, average="macro", zero_division=0
        )

        per_sample = [
            {
                "predicted": p,
                "reference": r,
                "correct": p == r,
            }
            for p, r in zip(pred_normalized, ref_normalized)
        ]

        return {
            "accuracy": round(accuracy, 4),
            "f1_macro": round(f1_macro, 4),
            "f1_weighted": round(f1_weighted, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "n_samples": len(predictions),
            "per_sample": per_sample[:50],
        }

    def evaluate_qa_exact_match(
        self, predictions: list[str], references: list[str]
    ) -> dict:
        def normalize(text: str) -> str:
            text = text.lower().strip()
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"[^\w\s]", "", text)
            return text

        correct = sum(
            1 for p, r in zip(predictions, references) if normalize(p) == normalize(r)
        )
        total = len(predictions)

        per_sample = [
            {
                "predicted": p,
                "reference": r,
                "exact_match": normalize(p) == normalize(r),
            }
            for p, r in zip(predictions, references)
        ]

        return {
            "exact_match": round(correct / max(total, 1), 4),
            "correct": correct,
            "total": total,
            "per_sample": per_sample[:50],
        }
