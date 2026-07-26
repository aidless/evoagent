from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


class VersionRegistry:
    def __init__(self, path: Path):
        self.path = path
        self.data = (
            json.loads(path.read_text(encoding="utf-8-sig"))
            if path.exists()
            else {"versions": {}, "history": []}
        )

    def audit(self, version_id=None, action=None, limit=20):
        rows = []
        for event in reversed(self.data.get("history") or []):
            if version_id and event.get("version_id") != version_id:
                continue
            if action and event.get("action") != action:
                continue
            rows.append(event)
            if len(rows) >= limit:
                break
        return {
            "version": version_id,
            "events": rows,
            "versions": self.data.get("versions", {}),
        }

    def activate(self, version_id):
        old = self.data["versions"][version_id]["level"]
        self.data["versions"][version_id]["level"] = "active"
        self.data["history"].append(
            {
                "action": "transition",
                "version_id": version_id,
                "from": old,
                "to": "active",
                "at": datetime.now(timezone.utc).isoformat(),
            }
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inspect the version audit trail")
    parser.add_argument("command", choices=("list", "audit"))
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--version")
    parser.add_argument("--action")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    registry = VersionRegistry(args.registry)
    if args.command == "list":
        result = {"versions": registry.data.get("versions", {})}
    else:
        result = registry.audit(args.version, args.action, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
