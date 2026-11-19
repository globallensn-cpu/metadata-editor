"""Reaboard Sensitive Field Registry and Privacy Classifier.

Maps EXIF, QuickTime, XMP, IPTC, ID3, and Document tags to privacy categories.
Provides partial masking for safe UI previews.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from apps.api.src.schemas.schemas import SensitivityCategory


@dataclass(frozen=True)
class SensitiveRule:
    category: SensitivityCategory
    pattern: re.Pattern[str]
    description: str


# Concrete regex rules matching sensitive metadata tags across all media types
RULES: list[SensitiveRule] = [
    # Location (GPS & Geolocation)
    SensitiveRule(
        SensitivityCategory.LOCATION,
        re.compile(
            r"^(GPS|Location|Coordinates|Latitude|Longitude|Altitude|DestLatitude|DestLongitude|Position|Geo|GPSCoordinates|GPSPosition)",
            re.IGNORECASE,
        ),
        "Geographic coordinates or altitude identifying physical location",
    ),
    # Device & Hardware
    SensitiveRule(
        SensitivityCategory.DEVICE,
        re.compile(
            r"^(Make|Model|CameraModelName|SerialNumber|InternalSerialNumber|LensSerialNumber|BodySerialNumber|CameraSerialNumber|LensModel|LensInfo|DeviceManufacturer|DeviceModel|UniqueID)",
            re.IGNORECASE,
        ),
        "Hardware model or unique serial numbers identifying a specific device",
    ),
    # Person & Identity
    SensitiveRule(
        SensitivityCategory.PERSON,
        re.compile(
            r"^(Author|Creator|Artist|OwnerName|CameraOwnerName|By-line|Credit|LastModifiedBy|Editor|Contributor|Writer|Composer|LeadPerformer|AccountName|Contact)",
            re.IGNORECASE,
        ),
        "Personal name, account, or creator identity",
    ),
    # Software & Digital Editing Workflow
    SensitiveRule(
        SensitivityCategory.SOFTWARE,
        re.compile(
            r"^(Software|ProcessingSoftware|CreatorTool|Application|WritingApp|WritingLibrary|HistorySoftwareAgent|HistoryAction|OriginalDocumentID|DocumentID|InstanceID|Encoder|Lavf|Lavc)",
            re.IGNORECASE,
        ),
        "Software suite, digital editing history, or unique file GUIDs",
    ),
    # Timestamps (Creation / Modification)
    SensitiveRule(
        SensitivityCategory.TIME,
        re.compile(
            r"^(CreateDate|DateTimeOriginal|ModifyDate|DateCreated|TimeCreated|TrackCreateDate|MediaCreateDate|CreationTime|MetadataDate)",
            re.IGNORECASE,
        ),
        "Precise creation or modification timestamp",
    ),
    # Network / Host
    SensitiveRule(
        SensitivityCategory.NETWORK,
        re.compile(
            r"^(ComputerName|HostComputer|IPAddress|BaseURL|URL|OriginatingHost)",
            re.IGNORECASE,
        ),
        "Network hostname or IP address of the processing machine",
    ),
]


def classify_tag(tag_name: str) -> tuple[bool, SensitivityCategory | None]:
    """Check if a metadata tag matches known sensitive patterns.
    
    Handles namespaced tags (e.g. 'QuickTime:GPSCoordinates', 'EXIF:Model').
    """
    clean_tag = tag_name.split(":")[-1]
    for rule in RULES:
        if rule.pattern.search(clean_tag):
            return True, rule.category
    return False, None


def mask_sensitive_value(category: SensitivityCategory | None, value: str) -> str:
    """Partially mask sensitive values for safe UI preview.

    Examples:
    - GPS: '37.7749 N, 122.4194 W' -> '37.77** N, 122.41** W'
    - Serial: 'G030VM12345678' -> 'G030********78'
    - Person: 'Johnathan Doe' -> 'Jo*********oe'
    """
    if not value or not isinstance(value, str):
        return "***"

    val_str = str(value).strip()
    if len(val_str) <= 2:
        return "***"

    if category == SensitivityCategory.LOCATION:
        # Mask lower decimal digits of latitude / longitude
        return re.sub(r"(\d+\.\d{2})\d+", r"\1**", val_str)

    if category in (SensitivityCategory.DEVICE, SensitivityCategory.PERSON, SensitivityCategory.NETWORK):
        if len(val_str) <= 4:
            return val_str[0] + "**"
        return f"{val_str[:2]}{'*' * (len(val_str) - 4)}{val_str[-2:]}"

    return val_str
