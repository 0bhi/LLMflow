import math

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.core.logging import get_logger

logger = get_logger("perplexity_eval")


class PerplexityEvaluator:
    """Compute perplexity on a held-out dataset."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self.tokenizer = None

    def setup(self) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_path)
        self.model.eval()
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def evaluate(self, texts: list[str], max_length: int = 512) -> dict:
        if not self.model or not self.tokenizer:
            self.setup()

        total_loss = 0.0
        total_tokens = 0
        per_sample: list[dict] = []

        for text in texts:
            encodings = self.tokenizer(
                text, return_tensors="pt", truncation=True, max_length=max_length
            )
            input_ids = encodings["input_ids"]
            target_ids = input_ids.clone()

            with torch.no_grad():
                outputs = self.model(input_ids=input_ids, labels=target_ids)
                loss = outputs.loss.item()

            n_tokens = input_ids.shape[1]
            total_loss += loss * n_tokens
            total_tokens += n_tokens
            per_sample.append({
                "text_preview": text[:100],
                "loss": round(loss, 4),
                "perplexity": round(math.exp(loss), 4),
                "n_tokens": n_tokens,
            })

        avg_loss = total_loss / max(total_tokens, 1)
        perplexity = math.exp(avg_loss)

        return {
            "perplexity": round(perplexity, 4),
            "avg_loss": round(avg_loss, 4),
            "total_tokens": total_tokens,
            "n_samples": len(texts),
            "per_sample": per_sample[:50],
        }
