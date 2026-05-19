from apt.utils.formats import is_valid_file


def test_empty_formats_rejects_everything():
    assert not is_valid_file("file.bmp", [])
    assert not is_valid_file("file.bmp", None)


def test_extension_match_is_case_insensitive():
    assert is_valid_file("IMAGE.BMP", [".bmp"])
    assert is_valid_file("image.bmp", [".BMP"])


def test_mim_matches():
    assert is_valid_file("foo.mim", [".mim"])
    assert not is_valid_file("foo.bmp", [".mim"])


def test_org_jpg_excludes_fov_in_basename():
    assert is_valid_file("normal.jpg", ["org_jpg"])
    assert not is_valid_file("fov_001.jpg", ["org_jpg"])


def test_fov_jpg_only_matches_fov_files():
    assert is_valid_file("fov_001.jpg", ["fov_jpg"])
    assert not is_valid_file("normal.jpg", ["fov_jpg"])


def test_multiple_formats_or_match():
    formats = ["fov_jpg", ".bmp"]
    assert is_valid_file("anything.bmp", formats)
    assert is_valid_file("fov_5.jpg", formats)
    assert not is_valid_file("normal.jpg", formats)
