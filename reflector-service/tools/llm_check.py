"""Simple script to verify the configured LLM provider directly.

Usage:
  python tools/llm_check.py

This will call the configured provider.complete() with a tiny system prompt
and payload. It prints the raw model output or the caught exception.
"""
import sys
from pathlib import Path

# ensure reflector-service package root on sys.path for local imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from config import settings
import json


def main():
    provider = get_provider()
    system, _ = prompt_registry.get_with_hash("reflector.system.txt")
    tagged = f"REFLECTOR_V3\n{system}\n\nReturn strict JSON only."
    sample_payload = {"request_id": "llm-check", "probe": True}
    user = json.dumps(sample_payload)

    print("Using provider:", provider.__class__.__name__)
    try:
        out = provider.complete(system_prompt=tagged, user_message=user)
        print("MODEL OUTPUT:\n", out)
    except Exception as exc:
        print("LLM call failed:")
        print(type(exc).__name__, str(exc))


if __name__ == "__main__":
    main()
