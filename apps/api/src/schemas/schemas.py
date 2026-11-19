"""Reaboard Domain Schemas (Pydantic v2).

Standardizes data contracts using camelCase on the wire (alias_generator=to_camel)
and snake_case internally, with timezone-aware datetimes and honest verification states.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model enforcing camelCase serialization on the wire."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class JobStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    CLEANING = "cleaning"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    EXPIRED = "expired"


class JobAction(StrEnum):
    VIEW = "view"
    REMOVE = "remove"


class SensitivityCategory(StrEnum):
    LOCATION = "location"
    DEVICE = "device"
    PERSON = "person"
    SOFTWARE = "software"
    TIME = "time"
    NETWORK = "network"
    OTHER = "other"


class SurvivorClass(StrEnum):
    STRUCTURAL = "structural"
    IDENTIFYING = "identifying"
    UNKNOWN = "unknown"


class CleaningMethod(StrEnum):
    REMUX = "remux"
    EXIFTOOL = "exiftool"
    EXIFTOOL_QPDF = "exiftool+qpdf"
    OFFICE_REPACK = "office-repack"
    AUDIO_STRIP = "audio-strip"
    REENCODE = "reencode"


class ErrorCode(StrEnum):
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    VERIFY_FAILED = "VERIFY_FAILED"
    REENCODE_REQUIRED = "REENCODE_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    INVALID_STATE = "INVALID_STATE"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"


# --- File Metadata Models ---

class FileInfo(CamelModel):
    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)

    original_filename: str = Field(..., description="Sanitized client filename for display/download")
    detected_mime: str = Field(..., description="MIME type confirmed by magic byte inspection")
    detected_type: str = Field(..., description="Normalized format (mp4, jpeg, png, pdf, etc.)")
    size_bytes: int = Field(..., ge=0, description="Exact file size in bytes")
    sha256: str = Field(..., min_length=64, max_length=64, description="Hex-encoded SHA-256 hash")


# --- View Metadata Models ---

class MetadataField(CamelModel):
    model_config = ConfigDict(frozen=True, alias_generator=to_camel, populate_by_name=True)

    group: str = Field(..., description="Metadata group/family (e.g. EXIF, QuickTime, XMP, ID3)")
    tag: str = Field(..., description="Tag name (e.g. GPSLatitude, Model, CreateDate)")
    value: Any = Field(..., description="Raw or formatted value")
    value_preview: str = Field(..., description="Masked or sanitized string representation")
    sensitive: bool = Field(default=False, description="Whether this field poses a privacy risk")
    category: SensitivityCategory | None = Field(default=None, description="Privacy risk classification")


class MetadataSection(CamelModel):
    name: str = Field(..., description="Section title (e.g. EXIF, GPS, Audio Stream, Container)")
    field_count: int = Field(..., ge=0)
    sensitive_count: int = Field(default=0, ge=0)
    fields: list[MetadataField] = Field(default_factory=list)


class C2PAManifestInfo(CamelModel):
    present: bool = Field(default=False)
    claim_generator: str | None = None
    title: str | None = None
    assertions_count: int = 0
    raw_summary: dict[str, Any] = Field(default_factory=dict)


class MetadataReport(CamelModel):
    job_id: str
    file_info: FileInfo
    sections: list[MetadataSection] = Field(default_factory=list)
    total_fields: int = Field(..., ge=0)
    sensitive_summary: dict[str, int] = Field(default_factory=dict)
    c2pa: C2PAManifestInfo = Field(default_factory=C2PAManifestInfo)
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Removal Options & Report Models ---

class RemovalOptions(CamelModel):
    keep_icc_profile: bool = Field(default=True, description="Preserve display color space (Images)")
    keep_orientation: bool = Field(default=True, description="Preserve visual display rotation")
    remove_c2pa: bool = Field(default=False, description="Deliberately remove C2PA Content Credentials")
    randomize_filename: bool = Field(default=False, description="Download with random UUID instead of original name")
    strip_office_authors: bool = Field(default=True, description="Remove author and last-modified fields from OOXML")
    allow_reencode: bool = Field(default=False, description="Allow lossy re-encode if lossless remux fails")


class RemovedField(CamelModel):
    group: str
    tag: str
    value_preview: str = Field(..., description="Partially masked preview of stripped content")
    category: SensitivityCategory | None = None


class SurvivorField(CamelModel):
    group: str
    tag: str
    survivor_class: SurvivorClass = Field(..., description="structural | identifying | unknown")
    value_preview: str
    reason: str = Field(..., description="Technical rationale for retaining this field")


class RemovalReport(CamelModel):
    job_id: str
    method: CleaningMethod
    method_reason: str
    pass_number: int = Field(default=1, description="1 for primary pass, 2 if secondary pass was triggered")
    size_before: int = Field(..., ge=0)
    size_after: int = Field(..., ge=0)
    playback_verified: bool = Field(default=False, description="True only when verified by playback check")
    stream_copy: bool | None = Field(
        default=None,
        description="True if verified lossless stream copy, False if re-encoded, None if N/A (images/docs)",
    )
    removed: list[RemovedField] = Field(default_factory=list)
    survivors: list[SurvivorField] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(
        ...,
        description="Keys: removed, survivorsIdentifying, survivorsStructural, survivorsUnknown",
    )
    hashes: dict[str, str] = Field(
        ...,
        description="Keys: originalSha256, cleanedSha256, originalStreamMd5, cleanedStreamMd5",
    )
    limits: list[str] = Field(
        default_factory=lambda: [
            "Original filename is not changed unless randomized name was opted in.",
            "Filesystem timestamps are created by your OS upon download.",
            "Content pixels, audio waveforms, visible text, watermarks, and PRNU sensor noise are not altered.",
            "Unknown or proprietary metadata tags outside the inspected registry cannot be guaranteed absent.",
        ]
    )
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --- Error Envelopes & Top-Level Job ---

class ErrorDetail(CamelModel):
    code: ErrorCode
    message: str
    hint: str | None = None
    request_id: str | None = None


class ErrorEnvelope(CamelModel):
    error: ErrorDetail


class Job(CamelModel):
    id: str
    batch_id: str | None = None
    status: JobStatus = JobStatus.CREATED
    action: JobAction | None = None
    file_info: FileInfo | None = None
    options: RemovalOptions | None = None
    progress_percent: int = Field(default=0, ge=0, le=100)
    current_stage: str = "created"
    error: ErrorDetail | None = None
    download_url: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
