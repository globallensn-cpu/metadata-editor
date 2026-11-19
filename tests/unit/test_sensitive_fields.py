"""Unit tests for Sensitive Field Classifier and Masking."""

import pytest
from apps.api.src.core.sensitive_fields import classify_tag, mask_sensitive_value
from apps.api.src.schemas.schemas import SensitivityCategory


def test_classify_location_tags():
    assert classify_tag("GPSLatitude") == (True, SensitivityCategory.LOCATION)
    assert classify_tag("QuickTime:GPSCoordinates") == (True, SensitivityCategory.LOCATION)
    assert classify_tag("Location") == (True, SensitivityCategory.LOCATION)
    assert classify_tag("Coordinates") == (True, SensitivityCategory.LOCATION)


def test_classify_device_tags():
    assert classify_tag("Model") == (True, SensitivityCategory.DEVICE)
    assert classify_tag("Make") == (True, SensitivityCategory.DEVICE)
    assert classify_tag("SerialNumber") == (True, SensitivityCategory.DEVICE)
    assert classify_tag("LensSerialNumber") == (True, SensitivityCategory.DEVICE)


def test_classify_person_tags():
    assert classify_tag("Author") == (True, SensitivityCategory.PERSON)
    assert classify_tag("Creator") == (True, SensitivityCategory.PERSON)
    assert classify_tag("Artist") == (True, SensitivityCategory.PERSON)
    assert classify_tag("LastModifiedBy") == (True, SensitivityCategory.PERSON)


def test_classify_structural_tags_not_sensitive():
    is_sens, cat = classify_tag("ImageWidth")
    assert not is_sens
    assert cat is None

    is_sens, cat = classify_tag("Duration")
    assert not is_sens


def test_mask_gps_coordinates():
    masked = mask_sensitive_value(SensitivityCategory.LOCATION, "+37.7749-122.4194/")
    assert "**" in masked
    assert "+37.77**" in masked


def test_mask_serial_and_person():
    masked_serial = mask_sensitive_value(SensitivityCategory.DEVICE, "SN123456789")
    assert masked_serial.startswith("SN")
    assert masked_serial.endswith("89")
    assert "*" in masked_serial

    masked_author = mask_sensitive_value(SensitivityCategory.PERSON, "John Smith")
    assert masked_author.startswith("Jo")
    assert masked_author.endswith("th")
