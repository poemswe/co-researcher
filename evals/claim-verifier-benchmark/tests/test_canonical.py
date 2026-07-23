import hashlib
import os

import pytest

from claim_verifier_benchmark.canonical import (
    ManifestError,
    build_manifest,
    canonical_bytes,
    manifest_digest,
)


def test_rfc8785_bytes_are_canonical():
    value = {"z": [3, 2, 1], "a": {"truth": True, "empty": None}}
    assert canonical_bytes(value) == (
        b'{"a":{"empty":null,"truth":true},"z":[3,2,1]}'
    )


def test_manifest_sorts_paths_and_hashes_exact_bytes(tmp_path):
    (tmp_path / "b.txt").write_bytes(b"beta\n")
    (tmp_path / "a.txt").write_bytes("café\n".encode("utf-8"))
    manifest = build_manifest(tmp_path, ["b.txt", "a.txt"])
    assert [item["path"] for item in manifest["files"]] == ["a.txt", "b.txt"]
    assert [item["size"] for item in manifest["files"]] == [6, 5]
    assert len(manifest_digest(manifest)) == 64


@pytest.mark.parametrize("bad", ["/absolute", "../escape", "x/../../escape"])
def test_manifest_rejects_unsafe_paths(tmp_path, bad):
    with pytest.raises(ManifestError):
        build_manifest(tmp_path, [bad])


def test_manifest_rejects_duplicates_and_symlinks(tmp_path):
    (tmp_path / "source.txt").write_text("source", encoding="utf-8")
    with pytest.raises(ManifestError):
        build_manifest(tmp_path, [])
    with pytest.raises(ManifestError):
        build_manifest(tmp_path, ["source.txt", "source.txt"])
    os.symlink(tmp_path / "source.txt", tmp_path / "link.txt")
    with pytest.raises(ManifestError):
        build_manifest(tmp_path, ["link.txt"])


def test_manifest_rejects_external_symlink_swapped_in_before_leaf_open(
    tmp_path, monkeypatch,
):
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    member = nested / "member.txt"
    member.write_bytes(b"trusted")
    external = tmp_path / "external.txt"
    external.write_bytes(b"external")

    real_open = os.open
    real_close = os.close
    opened: set[int] = set()
    closed: set[int] = set()
    swapped = False

    def racing_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if path == "member.txt" and dir_fd is not None and not swapped:
            member.unlink()
            member.symlink_to(external)
            swapped = True
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        opened.add(descriptor)
        return descriptor

    def tracking_close(descriptor):
        closed.add(descriptor)
        return real_close(descriptor)

    monkeypatch.setattr(os, "open", racing_open)
    monkeypatch.setattr(os, "close", tracking_close)

    with pytest.raises(ManifestError):
        build_manifest(root, ["nested/member.txt"])

    assert swapped
    assert opened
    assert opened == closed


def test_manifest_hashes_open_descriptor_after_pathname_is_swapped(
    tmp_path, monkeypatch,
):
    root = tmp_path / "root"
    root.mkdir()
    member = root / "member.txt"
    trusted = b"trusted descriptor bytes"
    member.write_bytes(trusted)
    external = tmp_path / "external.txt"
    external.write_bytes(b"external pathname bytes")

    real_open = os.open
    real_close = os.close
    real_fstat = os.fstat
    opened: set[int] = set()
    closed: set[int] = set()
    leaf_descriptor = None
    swapped = False

    def tracking_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal leaf_descriptor
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        opened.add(descriptor)
        if path == "member.txt" and dir_fd is not None:
            leaf_descriptor = descriptor
        return descriptor

    def racing_fstat(descriptor):
        nonlocal swapped
        if descriptor == leaf_descriptor and not swapped:
            member.unlink()
            member.symlink_to(external)
            swapped = True
        return real_fstat(descriptor)

    def tracking_close(descriptor):
        closed.add(descriptor)
        return real_close(descriptor)

    monkeypatch.setattr(os, "open", tracking_open)
    monkeypatch.setattr(os, "fstat", racing_fstat)
    monkeypatch.setattr(os, "close", tracking_close)

    manifest = build_manifest(root, ["member.txt"])

    assert swapped
    assert manifest["files"] == [{
        "path": "member.txt",
        "sha256": hashlib.sha256(trusted).hexdigest(),
        "size": len(trusted),
    }]
    assert opened == closed


def test_manifest_converts_descriptor_operation_failures_and_cleans_up(
    tmp_path, monkeypatch,
):
    (tmp_path / "member.txt").write_bytes(b"trusted")
    real_open = os.open
    real_close = os.close
    opened: set[int] = set()
    closed: set[int] = set()

    def tracking_open(path, flags, mode=0o777, *, dir_fd=None):
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        opened.add(descriptor)
        return descriptor

    def failing_fstat(_descriptor):
        raise RuntimeError("injected descriptor failure")

    def tracking_close(descriptor):
        closed.add(descriptor)
        return real_close(descriptor)

    monkeypatch.setattr(os, "open", tracking_open)
    monkeypatch.setattr(os, "fstat", failing_fstat)
    monkeypatch.setattr(os, "close", tracking_close)

    with pytest.raises(ManifestError, match="manifest root"):
        build_manifest(tmp_path, ["member.txt"])

    assert opened == closed
