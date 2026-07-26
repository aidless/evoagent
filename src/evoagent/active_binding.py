from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .core import candidate_id


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def build_active_binding(
    strategy: dict[str, Any],
    bundle: dict[str, Any],
    transaction_id: str,
    evidence_path: Path,
) -> dict[str, Any]:
    if not evidence_path.is_file():
        raise ValueError("evidence artifact is required")
    cid = candidate_id(strategy)
    bound_candidate = bundle.get("manifest", {}).get("metadata", {}).get("candidate_id")
    if bound_candidate != cid:
        raise ValueError("bundle is not bound to candidate")
    return {
        "schema_version": 1,
        "candidate_id": cid,
        "strategy_sha256": _canonical_sha256(strategy),
        "bundle_id": bundle["bundle_id"],
        "bundle_sha256": bundle["sha256"],
        "transaction_id": transaction_id,
        "evidence_path": str(evidence_path.resolve()),
        "evidence_sha256": _file_sha256(evidence_path),
    }


def verify_active_binding(
    binding: dict[str, Any],
    strategy: dict[str, Any],
    bundle: dict[str, Any],
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    cid = candidate_id(strategy)
    if binding.get("schema_version") != 1:
        reasons.append("unsupported_binding_schema")
    if binding.get("candidate_id") != cid:
        reasons.append("candidate_id_mismatch")
    if binding.get("strategy_sha256") != _canonical_sha256(strategy):
        reasons.append("strategy_hash_mismatch")
    if binding.get("bundle_id") != bundle.get("bundle_id"):
        reasons.append("bundle_id_mismatch")
    if binding.get("bundle_sha256") != bundle.get("sha256"):
        reasons.append("bundle_hash_mismatch")
    bound_candidate = bundle.get("manifest", {}).get("metadata", {}).get("candidate_id")
    if bound_candidate != cid:
        reasons.append("bundle_candidate_unbound")
    path = evidence_path or Path(str(binding.get("evidence_path", "")))
    if not path.is_file():
        reasons.append("evidence_missing")
    elif binding.get("evidence_sha256") != _file_sha256(path):
        reasons.append("evidence_hash_mismatch")
    if not binding.get("transaction_id"):
        reasons.append("transaction_id_missing")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "candidate_id": cid,
        "bundle_id": bundle.get("bundle_id"),
    }
