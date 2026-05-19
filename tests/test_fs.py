import os

from apt.utils.fs import copy_file_chunked, copy_folder_filtered, ensure_target_folder


def test_ensure_target_folder_creates_when_missing(tmp_path):
    target = tmp_path / "new" / "nested"
    assert not target.exists()
    assert ensure_target_folder(str(target))
    assert target.is_dir()


def test_ensure_target_folder_is_idempotent(tmp_path):
    target = tmp_path / "x"
    target.mkdir()
    assert ensure_target_folder(str(target))


def test_copy_file_chunked_copies_bytes(tmp_path):
    src = tmp_path / "src.bin"
    dst = tmp_path / "dst.bin"
    payload = b"abc" * 100_000
    src.write_bytes(payload)
    result = copy_file_chunked(str(src), str(dst))
    assert result.startswith("Copied")
    assert dst.read_bytes() == payload


def test_copy_file_chunked_respects_stop(tmp_path):
    src = tmp_path / "src.bin"
    dst = tmp_path / "dst.bin"
    src.write_bytes(b"x" * 4_000_000)
    result = copy_file_chunked(str(src), str(dst), is_stopped=lambda: True)
    assert result.startswith("오류 발생")
    assert not dst.exists()


def test_copy_folder_filtered_only_copies_matching(tmp_path, bmp_tree):
    target = tmp_path / "dst"
    result = copy_folder_filtered(str(bmp_tree), str(target), [".bmp"])
    assert result.startswith("Copied")
    # copy_folder_filtered only copies the *immediate* children of src.
    copied = sorted(p.name for p in target.iterdir())
    assert copied == ["top.bmp"]


def test_copy_folder_filtered_skips_when_no_match(tmp_path, bmp_tree):
    target = tmp_path / "dst"
    result = copy_folder_filtered(str(bmp_tree), str(target), [".jpg"])
    assert result.startswith("Copied 0")
