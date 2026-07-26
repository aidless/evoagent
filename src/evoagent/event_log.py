from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class EventLog:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def rows(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]

    def append(self, run_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self.rows()
        previous = rows[-1]["event_sha256"] if rows else ""
        body = {
            "event_id": uuid.uuid4().hex,
            "run_id": run_id,
            "sequence": len(rows) + 1,
            "event_type": event_type,
            "payload": payload,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "previous_event_sha256": previous,
        }
        body["event_sha256"] = hashlib.sha256(_canonical(body).encode()).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(body, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        return body

    def verify(self) -> dict[str, Any]:
        previous = ""
        reasons = []
        for expected_sequence, row in enumerate(self.rows(), 1):
            digest = row.get("event_sha256")
            body = {k: v for k, v in row.items() if k != "event_sha256"}
            actual = hashlib.sha256(_canonical(body).encode()).hexdigest()
            if row.get("sequence") != expected_sequence:
                reasons.append(f"sequence:{expected_sequence}")
            if row.get("previous_event_sha256") != previous:
                reasons.append(f"chain:{expected_sequence}")
            if digest != actual:
                reasons.append(f"hash:{expected_sequence}")
            previous = digest or ""
        return {"valid": not reasons, "reasons": reasons, "events": len(self.rows()), "head": previous}
