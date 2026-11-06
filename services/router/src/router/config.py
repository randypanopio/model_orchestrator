from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RouterSettings:
    api_key: str
    litellm_master_key: str
    litellm_base_url: str
    static_model: str
    model_tiers: dict[str, str]
    strategy: str

    @classmethod
    def from_env(cls) -> RouterSettings:
        api_key = os.environ.get("ROUTER_API_KEY", "")
        litellm_master_key = os.environ.get("LITELLM_MASTER_KEY", "")
        if not api_key:
            raise ValueError("ROUTER_API_KEY must be configured")
        if not litellm_master_key:
            raise ValueError("LITELLM_MASTER_KEY must be configured")

        config_path = Path(os.environ.get("MODEL_CONFIG_PATH", "config/models.yaml"))
        with config_path.open(encoding="utf-8") as config_file:
            config: Any = yaml.safe_load(config_file)

        if not isinstance(config, dict):
            raise ValueError(f"{config_path} must contain a YAML object")

        strategy = config.get("strategy")
        static_model = config.get("static_model")
        raw_tiers = config.get("tiers")
        if strategy != "static":
            raise ValueError(f"Unsupported router strategy: {strategy!r}")
        if not isinstance(static_model, str) or not static_model:
            raise ValueError("models.yaml must define a non-empty static_model")
        if not isinstance(raw_tiers, dict):
            raise ValueError("models.yaml must define model tiers")

        model_tiers: dict[str, str] = {}
        for tier, models in raw_tiers.items():
            if not isinstance(tier, str) or not isinstance(models, list):
                raise ValueError("Each model tier must map to a list of model aliases")
            for model in models:
                if not isinstance(model, str) or not model:
                    raise ValueError(f"Tier {tier!r} contains an invalid model alias")
                if model in model_tiers:
                    raise ValueError(f"Model alias {model!r} appears in multiple tiers")
                model_tiers[model] = tier

        if static_model not in model_tiers:
            raise ValueError(f"static_model {static_model!r} must be listed under a model tier")

        return cls(
            api_key=api_key,
            litellm_master_key=litellm_master_key,
            litellm_base_url=os.environ.get(
                "LITELLM_BASE_URL", "http://litellm:4000/v1"
            ).rstrip("/"),
            static_model=static_model,
            model_tiers=model_tiers,
            strategy=strategy,
        )
