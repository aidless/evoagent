from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from .attestation import hash_file
from .signing import SignatureRegistry, canonical_payload, sign_bundle


def load_trusted(path: Path):
    return {item.stem: item.read_bytes() for item in path.glob("*.pub")}


def verify_manifest_files(bundle: dict) -> dict:
    changed = []
    files = bundle.get("manifest", {}).get("files", {})
    for group, items in files.items():
        if not isinstance(items, dict):
            changed.append({"group": group, "reason": "invalid_file_manifest"})
            continue
        for raw_path, expected in items.items():
            path = Path(raw_path)
            actual = hash_file(path) if path.is_file() else None
            if actual != expected:
                changed.append(
                    {
                        "group": group,
                        "path": raw_path,
                        "expected": expected,
                        "actual": actual,
                    }
                )
    return {
        "valid": not changed,
        "reason": "ok" if not changed else "manifest_files_changed",
        "changed": changed,
    }


def verify_active_bundle(args) -> tuple[dict, int]:
    bundle_path = Path(args.bundles)
    signature_path = Path(args.signatures)
    trusted_path = Path(args.trusted)
    active_path = Path(args.active)
    if not active_path.exists():
        return {"promoted": False, "reason": "active_file_missing"}, 2
    active_id = active_path.read_text(encoding="utf-8-sig").strip()
    bundles = json.loads(bundle_path.read_text(encoding="utf-8-sig"))["bundles"]
    if active_id not in bundles:
        return {
            "promoted": False,
            "active_id": active_id,
            "reason": "active_not_in_registry",
        }, 3
    bundle = bundles[active_id]
    signature = SignatureRegistry(signature_path, load_trusted(trusted_path)).verify(bundle)
    if not signature["valid"]:
        return {
            "promoted": False,
            "active_id": active_id,
            "reason": signature["reason"],
        }, 4
    integrity = verify_manifest_files(bundle)
    if not integrity["valid"]:
        return {
            "promoted": False,
            "active_id": active_id,
            "reason": integrity["reason"],
            "changed": integrity["changed"],
        }, 5
    return {
        "promoted": True,
        "active_id": active_id,
        "verified": True,
        "manifest_integrity": True,
        "expires_at": signature.get("expires_at"),
        "signer": signature.get("signer"),
    }, 0


def cmd_generate(args):
    secret = Ed25519PrivateKey.generate()
    public = secret.public_key()
    private_path = Path(args.out_key)
    public_path = Path(args.out_pub)
    private_path.parent.mkdir(parents=True, exist_ok=True)
    public_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(
        secret.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    )
    public_path.write_bytes(public.public_bytes(Encoding.Raw, PublicFormat.Raw))
    print(json.dumps({"mode": "keygen", "key": args.out_key, "public_key": args.out_pub}))


def cmd_sign(args):
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8-sig"))
    private_key = Path(args.private_key).read_bytes()
    expires = datetime.now(timezone.utc) + timedelta(days=args.validity_days)
    envelope = sign_bundle(bundle, private_key, args.signer, expires.isoformat())
    Path(args.envelope).parent.mkdir(parents=True, exist_ok=True)
    Path(args.envelope).write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"envelope": str(args.envelope), "bundle_id": envelope["bundle_id"], "expires_at": envelope["expires_at"]}))


def cmd_request(args):
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8-sig"))
    request = {
        "bundle_id": bundle["bundle_id"],
        "bundle_sha256": bundle["sha256"],
        "signer": args.signer,
        "signed_at": None,
        "expires_at": None,
        "signature": None,
        "algorithm": "Ed25519",
        "payload_to_sign": canonical_payload(bundle["bundle_id"], bundle["sha256"], args.signer, "<ISO8601-UTC>", "<ISO8601-UTC>").decode(),
    }
    Path(args.output).write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"request": str(args.output)}))


def cmd_audit(args):
    registry = SignatureRegistry(Path(args.signatures), load_trusted(Path(args.trusted)))
    print(json.dumps(registry.audit(), ensure_ascii=False, indent=2))


def cmd_promote(args):
    payload, code = verify_active_bundle(args)
    print(json.dumps(payload))
    if code:
        raise SystemExit(code)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    command = sub.add_parser("generate")
    command.add_argument("--out-key", required=True)
    command.add_argument("--out-pub", required=True)
    command.set_defaults(func=cmd_generate)
    command = sub.add_parser("sign")
    command.add_argument("--bundle", required=True)
    command.add_argument("--private-key", required=True)
    command.add_argument("--envelope", required=True)
    command.add_argument("--signer", required=True)
    command.add_argument("--validity-days", type=int, default=30)
    command.set_defaults(func=cmd_sign)
    command = sub.add_parser("request")
    command.add_argument("--bundle", required=True)
    command.add_argument("--signer", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=cmd_request)
    command = sub.add_parser("audit")
    command.add_argument("--signatures", required=True)
    command.add_argument("--trusted", required=True)
    command.set_defaults(func=cmd_audit)
    command = sub.add_parser("promote")
    command.add_argument("--bundles", required=True)
    command.add_argument("--signatures", required=True)
    command.add_argument("--trusted", required=True)
    command.add_argument("--active", required=True)
    command.set_defaults(func=cmd_promote)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
