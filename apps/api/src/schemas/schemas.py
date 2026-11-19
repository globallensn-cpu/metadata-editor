"""Reaboard Domain Schemas (Pydantic v2).

Defines the complete data contract for jobs, metadata sections, sensitive classifications,
removal options, verified diff reports, and error envelopes.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    CREATED = "created"
    UPLOADED = "uploaded"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    CLEANING = "cleaning"
    VERIFYING = "verifying"
    COMPLETED = "completed"
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

class FileInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_filename: str = Field(..., description="Sanitized client filename for display/download")
    detected_mime: str = Field(..., description="MIME type confirmed by magic byte inspection")
    detected_type: str = Field(..., description="Normalized format (mp4, jpeg, png, etc.)")
    size_bytes: int = Field(..., ge=0, description="Exact file size in bytes")
    sha256: str = Field(..., min_length=64, max_length=64, description="Hex-encoded SHA-256 hash")


# --- View Metadata Models ---

class MetadataField(BaseModel):
    model_config = ConfigDict(frozen=True)

    group: str = Field(..., description="Metadata group/family (e.g. EXIF, QuickTime, XMP, ID3)")
    tag: str = Field(..., description="Tag name (e.g. GPSLatitude, Model, CreateDate)")
    value: Any = Field(..., description="Raw or formatted value")
    value_preview: str = Field(..., description="Masked or sanitized string representation")
    sensitive: bool = Field(default=False, description="Whether this field poses a privacy risk")
    category: SensitivityCategory | None = Field(default=None, description="Privacy risk classification")


class MetadataSection(BaseModel):
    name: str = Field(..., description="Section title (e.g. EXIF, GPS, Audio Stream, Container)")
    field_count: int = Field(..., ge=0)
    sensitive_count: int = Field(default=0, ge=0)
    fields: list[MetadataField] = Field(default_factory=list)


class C2PAManifestInfo(BaseModel):
    present: bool = Field(default=False)
    claim_generator: str | None = None
    title: str | None = None
    assertions_count: int = 0
    raw_summary: dict[str, Any] = Field(default_factory=dict)


class MetadataReport(BaseModel):
    job_id: str
    file_info: FileInfo
    sections: list[MetadataSection] = Field(default_factory=list)
    total_fields: int = Field(..., ge=0)
    sensitive_summary: dict[str, int] = Field(default_factory=dict)
    c2pa: C2PAManifestInfo = Field(default_factory=C2PAManifestInfo)
    extracted_at: datetime = Field(default_factory=datetime.utcnow)


# --- Removal Options & Report Models ---

class RemovalOptions(BaseModel):
    keep_icc_profile: bool = Field(default=True, description="Preserve display color space (Images)")
    keep_orientation: bool = Field(default=True, description="Preserve visual display rotation")
    remove_c2pa: bool = Field(default=False, description="Deliberately remove C2PA Content Credentials")
    randomize_filename: bool = Field(default=False, description="Download with random UUID instead of original name")
    strip_office_authors: bool = Field(default=True, description="Remove author and last-modified fields from OOXML")
    allow_reencode: bool = Field(default=False, description="Allow lossy re-encode if lossless remux fails")


class RemovedField(BaseModel):
    group: str
    tag: str
    value_preview: str = Field(..., description="Partially masked preview of stripped content")
    category: SensitivityCategory | None = None


class SurvivorField(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    group: str
    tag: str
    survivor_class: SurvivorClass = Field(alias="class")
    value_preview: str
    reason: str = Field(..., description="Technical rationale for retaining this field")


class RemovalReport(BaseModel):
    job_id: str
    method: CleaningMethod
    method_reason: str
    size_before: int = Field(..., ge=0)
    size_after: int = Field(..., ge=0)
    playback_verified: bool = Field(default=False)
    stream_copy: bool = Field(default=True)
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
            "File content (pixels, audio samples, visible text) is not modified.",
            "Watermarks, steganography, and sensor noise (PRNU) are not removed.",
            "File-system creation timestamps are governed by your operating system upon download.",
            "Original filename is preserved unless randomized download was chosen.",
        ]
    )
    completed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Error Envelopes & Top-Level Job ---

class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    hint: str | None = None
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class Job(BaseModel):
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
