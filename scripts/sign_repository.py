#!/usr/bin/env python3
"""Sign the official static device repository with an ECDSA P-256 key."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit


SIGNATURE_FILE = "repository.json.sig"
RESOURCE_DIRECTORIES = {
    "device": "devices",
    "rgb-model": "models",
    "canvas": "canvases",
}
RESOURCE_SUFFIXES = {
    "device": ".mgdevice.json",
    "rgb-model": ".mgmodel.json",
    "canvas": ".mgcanvas.json",
}


def run_openssl(args: list[str]) -> bytes:
    result = subprocess.run(
        ["openssl", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"openssl command failed: {detail or 'unknown error'}")
    return result.stdout


def sign_bytes(private_key: Path, content: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="mg-repository-sign-") as directory:
        payload = Path(directory) / "payload"
        signature = Path(directory) / "signature"
        payload.write_bytes(content)
        run_openssl(["dgst", "-sha256", "-sign", str(private_key), "-out", str(signature), str(payload)])
        return signature.read_bytes()


def verify_bytes(public_key: Path, content: bytes, signature: bytes) -> bool:
    with tempfile.TemporaryDirectory(prefix="mg-repository-verify-") as directory:
        payload = Path(directory) / "payload"
        signature_path = Path(directory) / "signature"
        payload.write_bytes(content)
        signature_path.write_bytes(signature)
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_key),
                "-signature",
                str(signature_path),
                str(payload),
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return result.returncode == 0 and result.stdout.strip() == b"Verified OK"


def decode_signature(value: object) -> bytes | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        return None


def _reject_encoded_path(path: str) -> None:
    if "%" in path:
        raise ValueError("downloadUrl must not contain percent-encoded path syntax")


def resolve_resource(root: Path, download_url: object, resource_type: object) -> Path:
    if not isinstance(download_url, str) or not download_url:
        raise ValueError("resource downloadUrl must be a non-empty relative path")
    if not isinstance(resource_type, str) or resource_type not in RESOURCE_SUFFIXES:
        raise ValueError("resource resourceType is unsupported")
    if "\\" in download_url or "?" in download_url or "#" in download_url:
        raise ValueError("resource downloadUrl contains a forbidden delimiter")
    _reject_encoded_path(download_url)
    parsed = urlsplit(download_url)
    if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
        raise ValueError("resource downloadUrl must be relative")
    parts = parsed.path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("resource downloadUrl contains unsafe path segments")
    expected_directory = RESOURCE_DIRECTORIES[resource_type]
    expected_suffix = RESOURCE_SUFFIXES[resource_type]
    if parts[0] != expected_directory or len(parts) != 2:
        raise ValueError("resource downloadUrl must use the canonical resource directory")
    if not parsed.path.endswith(expected_suffix):
        raise ValueError("resource downloadUrl has an invalid extension")
    stem = parsed.path.removeprefix(f"{expected_directory}/")[:-len(expected_suffix)]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", stem):
        raise ValueError("resource downloadUrl has an invalid resource file name")
    candidate = (root / parsed.path).resolve()
    root_resolved = root.resolve()
    if os.path.commonpath([str(root_resolved), str(candidate)]) != str(root_resolved):
        raise ValueError("resource downloadUrl escapes repository root")
    if not candidate.is_file():
        raise FileNotFoundError(f"resource file does not exist: {parsed.path}")
    return candidate


def verify_release_artifacts(root: Path, public_key: Path) -> None:
    repository_path = root / "repository.json"
    signature_path = root / SIGNATURE_FILE
    if not repository_path.is_file():
        raise ValueError("formal release requires repository.json")
    repository_bytes = repository_path.read_bytes()
    document = json.loads(repository_bytes)
    if "packages" in document:
        raise ValueError("repository.json must not contain packages")
    resources = document.get("resources")
    if not isinstance(resources, list):
        raise ValueError("repository resources must be an array")
    for entry in resources:
        if entry.get("signature") == "TEST-SIGNATURE-PENDING-OFFICIAL-RELEASE":
            raise ValueError("formal release cannot contain signature placeholder")
    if not signature_path.is_file():
        raise ValueError("formal release requires repository.json.sig")
    try:
        repository_signature = base64.b64decode(signature_path.read_text(encoding="ascii").strip(), validate=True)
    except (ValueError, UnicodeError) as error:
        raise ValueError("repository signature is not valid Base64") from error
    if not verify_bytes(public_key, repository_bytes, repository_signature):
        raise ValueError("repository signature verification failed")

    if document.get("schemaVersion") != 1:
        raise ValueError("repository.json schemaVersion must be 1")
    for entry in resources:
        signature_value = entry.get("signature")
        if signature_value == "TEST-SIGNATURE-PENDING-OFFICIAL-RELEASE":
            raise ValueError("formal release cannot contain signature placeholder")
        signature = decode_signature(signature_value)
        if signature is None:
            raise ValueError("resources entry signature is invalid")
        payload_path = resolve_resource(root, entry.get("downloadUrl"), entry.get("resourceType"))
        payload = payload_path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != entry.get("sha256"):
            raise ValueError("resources entry SHA-256 does not match payload")
        if not verify_bytes(public_key, payload, signature):
            raise ValueError("resources entry signature verification failed")


def canonical_json(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def load_private_public_key(private_key: Path, directory: Path) -> Path:
    public_key = directory / "official-public-key.pem"
    run_openssl(["pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)])
    return public_key


def sign_repository(root: Path, private_key: Path) -> bool:
    repository_path = root / "repository.json"
    if not repository_path.is_file():
        raise FileNotFoundError(repository_path)
    document = json.loads(repository_path.read_text(encoding="utf-8"))
    if document.get("schemaVersion") != 1:
        raise ValueError("repository.json schemaVersion must be 1")
    if document.get("repositoryId") != "official":
        raise ValueError("official repositoryId must be 'official'")
    if "packages" in document:
        raise ValueError("repository.json must not contain packages")
    resources = document.get("resources")
    if not isinstance(resources, list):
        raise ValueError("repository resources must be an array")

    with tempfile.TemporaryDirectory(prefix="mg-repository-key-") as directory_name:
        public_key = load_private_public_key(private_key, Path(directory_name))
        for entry in resources:
            if not isinstance(entry, dict):
                raise ValueError("repository resource entries must be objects")
            resource_path = resolve_resource(root, entry.get("downloadUrl"), entry.get("resourceType"))
            resource_bytes = resource_path.read_bytes()
            entry["sha256"] = hashlib.sha256(resource_bytes).hexdigest()
            existing = decode_signature(entry.get("signature"))
            if existing is None or not verify_bytes(public_key, resource_bytes, existing):
                entry["signature"] = base64.b64encode(sign_bytes(private_key, resource_bytes)).decode("ascii")

        repository_bytes = canonical_json(document)
        if repository_path.read_bytes() != repository_bytes:
            repository_path.write_bytes(repository_bytes)

        signature_path = root / SIGNATURE_FILE
        existing_repository_signature = None
        if signature_path.is_file():
            try:
                existing_repository_signature = base64.b64decode(
                    signature_path.read_text(encoding="ascii").strip(), validate=True
                )
            except (ValueError, UnicodeError):
                existing_repository_signature = None
        if existing_repository_signature is None or not verify_bytes(
            public_key, repository_bytes, existing_repository_signature
        ):
            signature_path.write_text(
                base64.b64encode(sign_bytes(private_key, repository_bytes)).decode("ascii") + "\n",
                encoding="ascii",
            )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--public-key", type=Path)
    parser.add_argument("--verify-release", action="store_true")
    args = parser.parse_args()

    root = args.repository_root.resolve()
    if args.verify_release:
        public_key = args.public_key.resolve() if args.public_key else root / "official-public-key.pem"
        if not public_key.is_file():
            parser.error("--verify-release requires --public-key or official-public-key.pem in the repository root")
        verify_release_artifacts(root, public_key)
        return 0
    if not args.private_key:
        parser.error("--private-key is required unless --verify-release is used")
    private_key = args.private_key.resolve()
    if not private_key.is_file():
        parser.error("private key file does not exist")
    sign_repository(root, private_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
