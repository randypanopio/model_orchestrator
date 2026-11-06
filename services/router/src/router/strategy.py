from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ModelChoice:
    model: str
    tier: str
    reason: str


class ModelStrategy(Protocol):
    def choose_model(self, request: dict[str, Any]) -> ModelChoice: ...


class StaticStrategy:
    def __init__(self, model: str, tier: str) -> None:
        self._model = model
        self._tier = tier

    def choose_model(self, request: dict[str, Any]) -> ModelChoice:
        del request
        return ModelChoice(
            model=self._model,
            tier=self._tier,
            reason="static strategy",
        )
