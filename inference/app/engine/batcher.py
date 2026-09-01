import asyncio

from app.models.loader import ModelManager


class RequestBatcher:
    """Serializes generate calls. Queue/window batching is not implemented."""

    def __init__(
        self,
        model_manager: ModelManager | None = None,
        max_batch_size: int = 8,
        max_wait_ms: float = 50.0,
    ):
        self.max_batch_size = max_batch_size
        self.max_wait_ms = max_wait_ms
        self._queue: asyncio.Queue = asyncio.Queue()
        self._model_manager = model_manager or ModelManager()
        self._lock = asyncio.Lock()

    @property
    def model_manager(self) -> ModelManager:
        return self._model_manager

    async def process(
        self,
        model_name: str,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
    ) -> dict:
        async with self._lock:
            result = await self._model_manager.generate(
                model_name=model_name,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        return result
