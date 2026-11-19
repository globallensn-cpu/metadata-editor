"""Unit tests for Strategy Selection."""

import pytest
from apps.api.src.schemas.schemas import CleaningMethod, RemovalOptions
from apps.worker.src.engine.strategy import (
    StrategySelectionError,
    select_cleaning_strategy,
)


def test_select_video_remux_strategy():
    method, reason = select_cleaning_strategy("mp4")
    assert method == CleaningMethod.REMUX
    assert "stream copy" in reason.lower()

    method, reason = select_cleaning_strategy("mov")
    assert method == CleaningMethod.REMUX


def test_select_image_exiftool_strategy():
    method, reason = select_cleaning_strategy("jpeg")
    assert method == CleaningMethod.EXIFTOOL

    method, reason = select_cleaning_strategy("png")
    assert method == CleaningMethod.EXIFTOOL


def test_unsupported_format_rejects_without_reencode():
    with pytest.raises(StrategySelectionError) as exc_info:
        select_cleaning_strategy("xyz_unknown", RemovalOptions(allow_reencode=False))
    assert exc_info.value.requires_reencode is True


def test_unsupported_format_permits_reencode_when_explicit():
    method, reason = select_cleaning_strategy("xyz_unknown", RemovalOptions(allow_reencode=True))
    assert method == CleaningMethod.REENCODE
    assert "user permitted" in reason.lower()
