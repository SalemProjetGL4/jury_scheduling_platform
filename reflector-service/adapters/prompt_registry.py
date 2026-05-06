from __future__ import annotations

import hashlib
from pathlib import Path


class PromptRegistry:
    def __init__(self, base_path: Path | None = None) -> None:
        self._base_path = base_path or Path(__file__).resolve().parent.parent / "prompts"

    def get(self, name: str) -> str:
        return (self._base_path / name).read_text(encoding="utf-8")

    def get_with_hash(self, name: str) -> tuple[str, str]:
        content = self.get(name)
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
        return content, digest


prompt_registry = PromptRegistry()
