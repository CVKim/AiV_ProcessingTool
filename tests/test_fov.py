from apt.utils.fov import extract_fov_from_filename, parse_fov_numbers


class TestParseFOVNumbers:
    def test_returns_none_on_empty(self):
        assert parse_fov_numbers("") is None
        assert parse_fov_numbers(None) is None

    def test_basic_comma_list(self):
        assert parse_fov_numbers("1,2,3") == {"1", "2", "3"}

    def test_with_range(self):
        assert parse_fov_numbers("1,2,3/5") == {"1", "2", "3", "4", "5"}

    def test_range_only(self):
        assert parse_fov_numbers("10/13") == {"10", "11", "12", "13"}

    def test_inverted_range_ignored(self):
        assert parse_fov_numbers("8/5,2") == {"2"}

    def test_invalid_tokens_skipped(self):
        assert parse_fov_numbers("abc,1,foo/bar,3") == {"1", "3"}

    def test_pure_garbage_returns_none(self):
        assert parse_fov_numbers("abc,foo/bar") is None


class TestExtractFOVFromFilename:
    def test_leading_digits(self):
        assert extract_fov_from_filename("12_image.bmp") == "12"

    def test_alphabetic_prefix_returns_none(self):
        assert extract_fov_from_filename("FOV_007.jpg") is None

    def test_mixed_prefix(self):
        # The legacy logic strips non-digits from the *prefix only* (before the
        # first underscore), so "13ab_x.bmp" yields "13".
        assert extract_fov_from_filename("13ab_x.bmp") == "13"

    def test_empty(self):
        assert extract_fov_from_filename("") is None
