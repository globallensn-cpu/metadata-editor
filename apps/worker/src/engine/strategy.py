"""Reaboard Strategy Selector.

Selects the appropriate cleaning pipeline based on magic-byte verified file types.
Enforces the lossless-by-default mandate.
"""

from __future__ import annotations

from apps.api.src.schemas.schemas import CleaningMethod, RemovalOptions


class StrategySelectionError(Exception):
    """Raised when no lossless strategy can be selected without re-encoding permission."""
    def __init__(self, message: str, requires_reencode: bool = False):
        super().__init__(message)
        self.requires_reencode = requires_reencode


def select_cleaning_strategy(
    detected_type: str,
    options: RemovalOptions | None = None,
) -> tuple[CleaningMethod, str]:
    """Select the cleaning pipeline for the detected format.

    Returns:
        (CleaningMethod, human_readable_method_reason)
    """
    opts = options or RemovalOptions()
    norm_type = detected_type.lower().strip()

    # Video Containers (Lossless Stream Copy)
    if norm_type in ("mp4", "mov", "m4v"):
        return (
            CleaningMethod.REMUX,
            "Lossless stream copy remuxing with bitexact flags, telemetry stream dropping, and handler blanking.",
        )

    if norm_type in ("mkv", "webm"):
        return (
            CleaningMethod.REMUX,
            "Matroska/WebM stream copy with global, chapter, and track tag stripping.",
        )

    if norm_type == "avi":
        return (
            CleaningMethod.REMUX,
            "AVI container stream copy preserving audio/video frames while clearing INFO chunks.",
        )

    # Images (Atomic ExifTool Sanitization)
    if norm_type in ("jpeg", "jpg", "png", "webp", "heic", "heif", "tiff"):
        features = []
        if opts.keep_icc_profile:
            features.append("ICC profile preserved")
        if opts.keep_orientation:
            features.append("Orientation preserved")
        feature_str = f" ({', '.join(features)})" if features else ""
        return (
            CleaningMethod.EXIFTOOL,
            f"Atomic ExifTool stripping of EXIF, GPS, XMP, IPTC, and thumbnails{feature_str}.",
        )

    # Documents: PDF
    if norm_type == "pdf":
        return (
            CleaningMethod.EXIFTOOL_QPDF,
            "Dual-pass ExifTool and QPDF linearization to purge incremental update object trees.",
        )

    # Documents: Office (OOXML)
    if norm_type in ("docx", "xlsx", "pptx"):
        return (
            CleaningMethod.OFFICE_REPACK,
            "ZIP package XML sanitization (docProps core/app/custom) and deterministic repack.",
        )

    # Audio Containers
    if norm_type in ("mp3", "m4a", "flac", "wav", "ogg"):
        return (
            CleaningMethod.AUDIO_STRIP,
            "Audio stream copy with ID3, Vorbis comments, APE, and embedded artwork stripping.",
        )

    # Fallback: check if reencode is permitted
    if opts.allow_reencode:
        return (
            CleaningMethod.REENCODE,
            "Transcoding fallback via visually transparent CRF encoding (user permitted).",
        )

    raise StrategySelectionError(
        f"Format '{detected_type}' cannot be cleaned losslessly without re-encoding.",
        requires_reencode=True,
    )
