from __future__ import annotations

import hashlib
import pathlib
from collections.abc import Iterable

import rfc8785

from .constants import PROTOCOL_CORE_VERSION


class ManifestError(ValueError):
    pass


def canonical_bytes(value: object) -> bytes:
    try:
        return rfc8785.dumps(value)
    except rfc8785.CanonicalizationError as exc:
        raise ManifestError(f"cannot canonicalize value: {exc}") from exc


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_relative_path(raw: str) -> pathlib.PurePosixPath:
    path = pathlib.PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ManifestError(f"unsafe relative path: {raw!r}")
    if path.as_posix() != raw:
        raise ManifestError(f"path is not canonical POSIX form: {raw!r}")
    return path


def build_manifest(
    root: pathlib.Path,
    relative_paths: Iterable[str],
) -> dict:
    root = root.resolve(strict=True)
    seen: set[str] = set()
    files: list[dict] = []
    for raw in relative_paths:
        path = _safe_relative_path(raw)
        normalized = path.as_posix()
        if normalized in seen:
            raise ManifestError(f"duplicate manifest path: {normalized}")
        seen.add(normalized)
        disk_path = root.joinpath(*path.parts)
        cursor = root
        for part in path.parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise ManifestError(f"manifest path contains a symlink: {normalized}")
        if not disk_path.is_file():
            raise ManifestError(f"manifest member is not a regular file: {normalized}")
        resolved = disk_path.resolve(strict=True)
        if not resolved.is_relative_to(root):
            raise ManifestError(f"manifest member escapes root: {normalized}")
        payload = disk_path.read_bytes()
        files.append({
            "path": normalized,
            "sha256": sha256_hex(payload),
            "size": len(payload),
        })
    if not files:
        raise ManifestError("manifest must contain at least one file")
    return {
        "protocol_core_version": PROTOCOL_CORE_VERSION,
        "files": sorted(files, key=lambda item: item["path"].encode("utf-8")),
    }


def manifest_digest(manifest: dict) -> str:
    return sha256_hex(canonical_bytes(manifest))
