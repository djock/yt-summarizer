import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fetch import validate_channel_handle


class TestValidateChannelHandle:
    def test_valid_simple_handle(self):
        validate_channel_handle("@MyChannel")  # should not raise

    def test_valid_with_numbers(self):
        validate_channel_handle("@channel123")

    def test_valid_with_dots(self):
        validate_channel_handle("@my.channel")

    def test_valid_with_hyphens(self):
        validate_channel_handle("@my-channel")

    def test_valid_with_underscores(self):
        validate_channel_handle("@my_channel")

    def test_valid_uppercase(self):
        validate_channel_handle("@SAM_SULEK")

    def test_missing_at_sign_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("MyChannel")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("")

    def test_only_at_sign_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("@")

    def test_spaces_in_handle_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("@my channel")

    def test_url_style_raises(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("https://youtube.com/@channel")

    def test_special_chars_raise(self):
        with pytest.raises(ValueError, match="Invalid channel handle"):
            validate_channel_handle("@chan!nel")

    def test_error_message_includes_bad_value(self):
        with pytest.raises(ValueError, match="badvalue"):
            validate_channel_handle("badvalue")
