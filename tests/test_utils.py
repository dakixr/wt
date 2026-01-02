"""Tests for wt.utils module."""
import pytest

from wt.errors import InvalidFeatureNameError
from wt.utils import derive_feat_name_from_branch, normalize_feat_name


class TestNormalizeFeatName:
    def test_lowercase(self) -> None:
        assert normalize_feat_name("MyFeature") == "myfeature"

    def test_spaces_to_dashes(self) -> None:
        assert normalize_feat_name("my feature") == "my-feature"

    def test_valid_chars(self) -> None:
        assert normalize_feat_name("feat-1.0_test") == "feat-1.0_test"

    def test_invalid_chars_raises(self) -> None:
        with pytest.raises(InvalidFeatureNameError):
            normalize_feat_name("feat@name")


class TestDeriveFeatName:
    def test_strips_prefix(self) -> None:
        assert derive_feat_name_from_branch("feature/billing", "feature/") == "billing"

    def test_no_prefix(self) -> None:
        assert derive_feat_name_from_branch("billing", "feature/") == "billing"
