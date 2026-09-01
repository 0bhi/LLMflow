import os

import structlog

from app.core.storage import download_artifact

logger = structlog.get_logger()


class ModelManager:
    """Manages loading and inference for HuggingFace models with PEFT adapters."""

    def __init__(self):
        self._models: dict[str, object] = {}
        self._tokenizers: dict[str, object] = {}
        self._deployed_ids: dict[str, int] = {}

    async def load_model(
        self,
        model_name: str,
        model_path: str,
        deployed_model_id: int | None = None,
        **kwargs,
    ) -> None:
        try:
            from peft import PeftConfig, PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer

            local_path = model_path
            if not os.path.isdir(model_path):
                local_path = download_artifact(model_path)

            adapter_config = os.path.join(local_path, "adapter_config.json")
            if os.path.exists(adapter_config):
                peft_config = PeftConfig.from_pretrained(local_path)
                model = AutoModelForCausalLM.from_pretrained(
                    peft_config.base_model_name_or_path, **kwargs
                )
                model = PeftModel.from_pretrained(model, local_path)
                tokenizer = AutoTokenizer.from_pretrained(local_path)
            else:
                tokenizer = AutoTokenizer.from_pretrained(local_path)
                model = AutoModelForCausalLM.from_pretrained(local_path, **kwargs)

            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model.eval()
            self._models[model_name] = model
            self._tokenizers[model_name] = tokenizer
            if deployed_model_id is not None:
                self._deployed_ids[model_name] = deployed_model_id
            logger.info("model_loaded", model_name=model_name, path=local_path)
        except Exception as e:
            logger.error("model_load_failed", model_name=model_name, error=str(e))
            raise

    async def generate(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> dict:
        if model_name not in self._models:
            return {
                "completion": f"[Model '{model_name}' not loaded. This is a placeholder response.]",
                "tokens_in": len(prompt.split()),
                "tokens_out": 10,
                "deployed_model_id": self._deployed_ids.get(model_name),
                "placeholder": True,
            }

        model = self._models[model_name]
        tokenizer = self._tokenizers[model_name]

        inputs = tokenizer(prompt, return_tensors="pt")
        tokens_in = inputs["input_ids"].shape[1]

        import torch

        max_new = max(1, min(max_tokens, 64))
        sampling = temperature > 0
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new,
                temperature=temperature if sampling else 1.0,
                do_sample=sampling,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
                repetition_penalty=1.2,
            )

        tokens_out = outputs.shape[1] - tokens_in
        completion = tokenizer.decode(outputs[0][tokens_in:], skip_special_tokens=True)
        for stop in ("### Instruction", "### Input", "\n###"):
            if stop in completion:
                completion = completion.split(stop, 1)[0]
        completion = completion.strip()

        return {
            "completion": completion,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "deployed_model_id": self._deployed_ids.get(model_name),
        }

    def is_loaded(self, model_name: str) -> bool:
        return model_name in self._models

    def list_loaded(self) -> list[str]:
        return list(self._models.keys())
