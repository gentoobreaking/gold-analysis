"""Trade event logging (JSONL).

Every order submission, fill, rejection and position-sync mismatch is appended
as one JSON line so the audit trail is append-only and trivially queryable.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

_DEFAULT_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


class TradeLogger:
    """Append-only JSONL trade log."""

    def __init__(self, path: str | None = None):
        # Resolve at call time so GOLD_TRADE_LOG_DIR (per-deploy) is honoured.
        base = os.environ.get("GOLD_TRADE_LOG_DIR", _DEFAULT_LOG_DIR)
        self.path = path or os.path.join(base, "trades.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def log(self, event: dict[str, Any]) -> None:
        event = dict(event)
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, default=str) + "\n")

    def read(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        out: list[dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out
