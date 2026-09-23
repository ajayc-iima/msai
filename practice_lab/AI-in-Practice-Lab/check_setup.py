#!/usr/bin/env python3
"""Environment check. You are ready when the last line reads: Environment is ready.

    python check_setup.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, fix: str = "") -> None:
    CHECKS.append((name, ok, fix))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if not ok and fix:
        print(f"        -> {fix}")


def main() -> None:
    print(f"python {sys.version.split()[0]} at {sys.executable}")
    check("python is 3.11+", sys.version_info >= (3, 11),
          "install Python 3.11-3.14 3.15+ has no support yet across provider SDKs")

    for mod in ("pydantic", "dotenv", "httpx"):
        try:
            __import__(mod)
            check(f"import {mod}", True)
        except ImportError:
            check(f"import {mod}", False, f"pip install -r requirements.txt")

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    key = os.getenv("GEMINI_API_KEY", "")
    profile = os.getenv("AIP_PROFILE", "gemini")
    check("GEMINI_API_KEY set", bool(key.strip()),
          "create .env in the repo root with GEMINI_API_KEY=AIza... (no quotes, no spaces)")

    if key.strip() and profile == "gemini":
        try:
            from aip import chat
            text = chat("Reply with exactly: ok", tier="SMALL", max_tokens=500)
            check("live model call", "ok" in text.lower(),
                  "404/model-not-found: the model id rotted — edit PROFILES in "
                  "aip/config.py. 429: rate limited, wait 60s and retry.")
        except Exception as exc:  # noqa: BLE001
            check("live model call", False, f"{type(exc).__name__}: {exc}")

    print()
    if all(ok for _, ok, _ in CHECKS):
        print("Environment is ready.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
