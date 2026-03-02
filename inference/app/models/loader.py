import structlog

logger = structlog.get_logger()


class ModelManager:
    """Manages loading and inference for HuggingFace models with PEFT adapters."""

    def __init__(self):
        self._models: dict[str, object] = {}
        self._tokenizers: dict[str, object] = {}

    async def load_model(self, model_name: str, model_path: str, **kwargs) -> None:
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(model_path, **kwargs)

            self._models[model_name] = model
            self._tokenizers[model_name] = tokenizer
            logger.info("model_loaded", model_name=model_name, path=model_path)
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
            }

        model = self._models[model_name]
        tokenizer = self._tokenizers[model_name]

        inputs = tokenizer(prompt, return_tensors="pt")
        tokens_in = inputs["input_ids"].shape[1]

        import torch

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature if temperature > 0 else 1.0,
                do_sample=temperature > 0,
            )

        tokens_out = outputs.shape[1] - tokens_in
        completion = tokenizer.decode(outputs[0][tokens_in:], skip_special_tokens=True)

        return {
            "completion": completion,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    def is_loaded(self, model_name: str) -> bool:
        return model_name in self._models
