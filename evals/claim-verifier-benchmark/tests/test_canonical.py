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
