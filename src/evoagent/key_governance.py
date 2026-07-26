from __future__ import annotations

from pathlib import Path


def audit_key_directory(path: Path) -> dict:
    private = sorted(
        str(item)
        for item in path.rglob("*")
        if item.is_file() and item.suffix.lower() in {".priv", ".key", ".pem"}
    )
    public = sorted(str(item) for item in path.glob("*.pub") if item.is_file())
    return {
        "valid": not private,
        "reason": "ok" if not private else "private_key_in_trust_store",
        "public_keys": public,
        "private_keys": private,
    }
