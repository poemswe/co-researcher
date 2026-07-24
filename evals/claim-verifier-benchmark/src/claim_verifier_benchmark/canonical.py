from __future__ import annotations

import hashlib
import os
import pathlib
import stat
from collections.abc import Iterable

import rfc8785

from .constants import PROTOCOL_CORE_VERSION

_OPEN_SUPPORTS_DIR_FD = os.open in getattr(os, "supports_dir_fd", ())
_READ_SIZE = 1024 * 1024


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
    if type(raw) is not str:
        raise ManifestError("manifest paths must be strings")
    path = pathlib.PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ManifestError(f"unsafe relative path: {raw!r}")
    if path.as_posix() != raw:
        raise ManifestError(f"path is not canonical POSIX form: {raw!r}")
    return path


def _secure_open_flags(*, directory: bool) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    directory_only = getattr(os, "O_DIRECTORY", 0)
    required_operations = ("open", "close", "fstat", "read")
    if (
        not _OPEN_SUPPORTS_DIR_FD
        or not no_follow
        or not directory_only
        or not all(callable(getattr(os, name, None)) for name in required_operations)
    ):
        raise ManifestError(
            "secure manifest traversal requires descriptor-relative open, "
            "O_NOFOLLOW, O_DIRECTORY, fstat, read, and close"
        )
    flags = os.O_RDONLY | no_follow | getattr(os, "O_CLOEXEC", 0)
    return flags | directory_only if directory else flags


def _close_descriptors(descriptors: list[int]) -> None:
    close_error: Exception | None = None
    for descriptor in reversed(descriptors):
        try:
            os.close(descriptor)
        except Exception as exc:
            close_error = exc
    if close_error is not None:
        raise close_error


def _read_manifest_member(
    root_descriptor: int,
    path: pathlib.PurePosixPath,
    normalized: str,
) -> bytes:
    descriptors: list[int] = []
    try:
        parent_descriptor = root_descriptor
        for part in path.parts[:-1]:
            descriptor = os.open(
                part,
                _secure_open_flags(directory=True),
                dir_fd=parent_descriptor,
            )
            descriptors.append(descriptor)
            parent_descriptor = descriptor
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise ManifestError(
                    f"manifest path component is not a directory: {normalized}"
                )

        leaf_descriptor = os.open(
            path.parts[-1],
            _secure_open_flags(directory=False),
            dir_fd=parent_descriptor,
        )
        descriptors.append(leaf_descriptor)
        if not stat.S_ISREG(os.fstat(leaf_descriptor).st_mode):
            raise ManifestError(
                f"manifest member is not a regular file: {normalized}"
            )

        chunks: list[bytes] = []
        while chunk := os.read(leaf_descriptor, _READ_SIZE):
            chunks.append(chunk)
        return b"".join(chunks)
    except ManifestError:
        raise
    except Exception as exc:
        raise ManifestError(
            f"cannot securely open manifest member {normalized!r}: {exc}"
        ) from exc
    finally:
        try:
            _close_descriptors(descriptors)
        except Exception as exc:
            raise ManifestError(
                f"cannot close manifest member {normalized!r}: {exc}"
            ) from exc


def build_manifest(
    root: pathlib.Path,
    relative_paths: Iterable[str],
) -> dict:
    seen: set[str] = set()
    files: list[dict] = []
    root_descriptor: int | None = None
    try:
        root_descriptor = os.open(root, _secure_open_flags(directory=True))
        if not stat.S_ISDIR(os.fstat(root_descriptor).st_mode):
            raise ManifestError("manifest root is not a directory")
        for raw in relative_paths:
            path = _safe_relative_path(raw)
            normalized = path.as_posix()
            if normalized in seen:
                raise ManifestError(f"duplicate manifest path: {normalized}")
            seen.add(normalized)
            payload = _read_manifest_member(root_descriptor, path, normalized)
            files.append({
                "path": normalized,
                "sha256": sha256_hex(payload),
                "size": len(payload),
            })
    except ManifestError:
        raise
    except Exception as exc:
        raise ManifestError(f"cannot securely open manifest root: {exc}") from exc
    finally:
        if root_descriptor is not None:
            try:
                os.close(root_descriptor)
            except Exception as exc:
                raise ManifestError(
                    f"cannot close manifest root descriptor: {exc}"
                ) from exc
    if not files:
        raise ManifestError("manifest must contain at least one file")
    return {
        "protocol_core_version": PROTOCOL_CORE_VERSION,
        "files": sorted(files, key=lambda item: item["path"].encode("utf-8")),
    }


def manifest_digest(manifest: dict) -> str:
    return sha256_hex(canonical_bytes(manifest))
