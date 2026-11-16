"""Model registry: the single source of truth for which models exist, who owns them, and
whether they may be used right now. Setting `enabled: false` is the kill switch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class ModelNotAllowed(Exception):
    """Raised when a caller asks for a model that is unknown or switched off."""


@dataclass(frozen=True)
class ModelEntry:
    name: str  # the name the inference backend knows the model by, e.g. "qwen2.5:1.5b"
    owner: str
    license: str
    source: str  # where the weights came from (provenance)
    enabled: bool
    max_output_tokens: int


class Registry:
    def __init__(self, entries: dict[str, ModelEntry]):
        self._entries = entries

    @classmethod
    def load(cls, path: Path) -> Registry:
        raw = yaml.safe_load(path.read_text()) or {}
        entries = {}
        for alias, spec in (raw.get("models") or {}).items():
            entries[alias] = ModelEntry(
                name=spec["name"],
                owner=spec["owner"],
                license=spec["license"],
                source=spec["source"],
                enabled=bool(spec.get("enabled", True)),
                max_output_tokens=int(spec.get("max_output_tokens", 512)),
            )
        return cls(entries)

    def list(self) -> dict[str, ModelEntry]:
        return dict(self._entries)

    def resolve(self, alias: str) -> ModelEntry:
        entry = self._entries.get(alias)
        if entry is None:
            raise ModelNotAllowed(f"Model '{alias}' is not in the registry.")
        if not entry.enabled:
            raise ModelNotAllowed(f"Model '{alias}' is switched off in the registry (kill switch).")
        return entry
