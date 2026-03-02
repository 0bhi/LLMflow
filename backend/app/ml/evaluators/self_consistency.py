from collections import Counter

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from app.core.logging import get_logger

logger = get_logger("self_consistency")


class SelfConsistencyChecker:
    """
    Generate N completions for each prompt. Flag prompts where
    completions disagree, indicating potential hallucination.
    """

    def __init__(self, model_path: str, n_samples: int = 5, temperature: float = 0.8):
        self.model_path = model_path
        self.n_samples = n_samples
        self.temperature = temperature
        self.model = None
        self.tokenizer = None

    def setup(self) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForCausalLM.from_pretrained(self.model_path)
        self.model.eval()
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def _generate_completions(self, prompt: str, max_tokens: int = 100) -> list[str]:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        completions = []

        for _ in range(self.n_samples):
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=self.temperature,
                    do_sample=True,
                    top_p=0.95,
                )
            tokens_in = inputs["input_ids"].shape[1]
            completion = self.tokenizer.decode(outputs[0][tokens_in:], skip_special_tokens=True)
            completions.append(completion.strip())

        return completions

    def _compute_agreement(self, completions: list[str]) -> float:
        if not completions:
            return 0.0
        counter = Counter(completions)
        most_common_count = counter.most_common(1)[0][1]
        return most_common_count / len(completions)

    def evaluate(self, prompts: list[str], max_tokens: int = 100) -> dict:
        if not self.model or not self.tokenizer:
            self.setup()

        results: list[dict] = []
        flagged = 0

        for prompt in prompts:
            completions = self._generate_completions(prompt, max_tokens)
            agreement = self._compute_agreement(completions)
            is_consistent = agreement >= 0.6

            if not is_consistent:
                flagged += 1

            results.append({
                "prompt_preview": prompt[:100],
                "n_completions": len(completions),
                "agreement_score": round(agreement, 4),
                "is_consistent": is_consistent,
                "unique_answers": len(set(completions)),
                "completions": completions[:3],
            })

        total = len(prompts)
        consistency_rate = (total - flagged) / max(total, 1)

        return {
            "consistency_rate": round(consistency_rate, 4),
            "flagged_count": flagged,
            "total_prompts": total,
            "n_samples_per_prompt": self.n_samples,
            "per_sample": results[:50],
        }
