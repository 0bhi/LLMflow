import random


class ABRouter:
    """Routes requests across model versions based on traffic percentage."""

    def __init__(self):
        self._routes: dict[str, float] = {}
        self._default_model: str = "default"

    def set_route(self, model_name: str, traffic_pct: float) -> None:
        self._routes[model_name] = traffic_pct

    def remove_route(self, model_name: str) -> None:
        self._routes.pop(model_name, None)

    def route(self, requested_model: str | None = None) -> str:
        if requested_model:
            return requested_model

        if not self._routes:
            return self._default_model

        roll = random.random() * 100
        cumulative = 0.0
        for model, pct in self._routes.items():
            cumulative += pct
            if roll < cumulative:
                return model

        return list(self._routes.keys())[-1]

    def list_models(self) -> list[str]:
        return list(self._routes.keys()) or [self._default_model]
