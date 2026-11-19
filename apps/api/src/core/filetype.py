"""Reaboard File Type Detection & Security Bomb Validation Engine.

Inspects up to 64 KB of file headers using magic byte signatures, parses container atoms
(ftyp brands, EBML DocTypes, OOXML ZIP contents), and enforces decompression/archive bomb guards.
"""

from __future__ import annotations

import io
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

# Archive bomb constraints for OOXML / ZIP containers
MAX_ZIP_ENTRIES = 500
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_ZIP_COMPRESSION_RATIO = 10.0

# Image dimensions limit (100 Megapixels)
MAX_IMAGE_PIXELS = 100_000_000


class FileTypeError(Exception):
    """Base exception for file type detection and validation errors."""

    def __init__(self, message: str, code: str = "UNSUPPORTED_TYPE", hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.hint = hint


class FileTypeMismatchError(FileTypeError):
    """Raised when file extension conflicts dangerously with detected magic byte signature."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message, code="TYPE_MISMATCH", hint=hint)


class UnsupportedFileTypeError(FileTypeError):
    """Raised when file format is not supported or signature is unknown."""

    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message, code="UNSUPPORTED_TYPE", hint=hint)


@dataclass(frozen=True)
class DetectedType:
    normalized_type: str
    mime_type: str
    description: str


def _parse_ftyp_brands(header: bytes) -> tuple[str, list[str]]:
    """Extract major brand and compatible brands from an ISO Base Media File Format ftyp box."""
    if len(header) < 16:
        return "", []

    box_len = struct.unpack(">I", header[0:4])[0]
    box_type = header[4:8]

    if box_type != b"ftyp":
        return "", []

    major_brand = header[8:12].decode("latin1", errors="replace")
    compatible_brands = []

    # Read compatible brands (4 bytes each until end of box or header)
    limit = min(box_len, len(header))
    for i in range(16, limit, 4):
        if i + 4 <= limit:
            brand = header[i : i + 4].decode("latin1", errors="replace")
            compatible_brands.append(brand)

    return major_brand, compatible_brands


def _detect_ebml_doctype(header: bytes) -> str:
    """Inspect EBML header to distinguish between WebM and Matroska (MKV)."""
    # Look for DocType element string in initial EBML bytes
    if b"webm" in header[:2048]:
        return "webm"
    if b"matroska" in header[:2048]:
        return "mkv"
    return "mkv"  # Default Matroska container


def _validate_and_classify_ooxml(file_bytes: bytes) -> tuple[str, str]:
    """Validate OOXML ZIP package for zip bombs and determine exact document format from content."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            infos = z.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise FileTypeError(
                    f"ZIP package exceeds maximum entry limit ({len(infos)} > {MAX_ZIP_ENTRIES})",
                    code="FILE_TOO_LARGE",
                    hint="Archive contains too many internal files (potential zip bomb).",
                )

            total_compressed = sum(info.compress_size for info in infos)
            total_uncompressed = sum(info.file_size for info in infos)

            if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                raise FileTypeError(
                    f"ZIP uncompressed size exceeds limit ({total_uncompressed} > {MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES})",
                    code="FILE_TOO_LARGE",
                    hint="Decompression exceeds maximum allowable memory budget.",
                )

            if total_compressed > 0:
                ratio = total_uncompressed / total_compressed
                if ratio > MAX_ZIP_COMPRESSION_RATIO:
                    raise FileTypeError(
                        f"Suspicious compression ratio detected ({ratio:.1f}:1 > {MAX_ZIP_COMPRESSION_RATIO}:1)",
                        code="FILE_TOO_LARGE",
                        hint="Potential decompression bomb detected.",
                    )

            # Inspect [Content_Types].xml or internal directory structure
            names = set(z.namelist())
            if "[Content_Types].xml" not in names:
                raise FileTypeError(
                    "Missing [Content_Types].xml in Office document package.",
                    code="TYPE_MISMATCH",
                )

            ct_bytes = z.read("[Content_Types].xml").decode("utf-8", errors="ignore")

            if "wordprocessingml" in ct_bytes or "word/" in names:
                return "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if "spreadsheetml" in ct_bytes or "xl/" in names:
                return "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if "presentationml" in ct_bytes or "ppt/" in names:
                return "pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"

            raise FileTypeError(
                "ZIP archive is not a recognized Office Open XML document (DOCX, XLSX, PPTX).",
                code="UNSUPPORTED_TYPE",
                hint="Only DOCX, XLSX, and PPTX documents are supported.",
            )
    except zipfile.BadZipFile:
        raise FileTypeError("Corrupted or invalid ZIP archive.", code="TYPE_MISMATCH")


def detect_file_type(header: bytes, filename: str = "", full_bytes: bytes | None = None) -> DetectedType:
    """Detect file type and MIME type from at least 64 KB of file header.

    Enforces hostile payload rejection and strict brand classification.
    """
    if len(header) < 12:
        raise FileTypeError("File is truncated or too small to identify format signature.")

    # 1. Hostile payload rejection (Executables, Scripts, Polyglots)
    if header.startswith(b"MZ") or header.startswith(b"\x7fELF") or header.startswith(b"\xca\xfe\xba\xbe"):
        raise FileTypeError(
            "Executable binaries (PE/ELF/Mach-O) are strictly forbidden.",
            code="TYPE_MISMATCH",
            hint="Do not disguise executable files with media extensions.",
        )

    stripped = header.lstrip()
    if (
        stripped.startswith(b"#!")
        or stripped.startswith(b"<?php")
        or stripped.startswith(b"<html")
        or stripped.startswith(b"<script")
    ):
        raise FileTypeError(
            "Script or markup source file disguised as media is rejected.",
            code="TYPE_MISMATCH",
            hint="Upload valid binary media files only.",
        )

    # 2. Out of scope formats (GIF)
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        raise FileTypeError(
            "GIF animation format is explicitly out of scope for Reaboard.",
            code="UNSUPPORTED_TYPE",
            hint="Supported image formats: JPEG, PNG, WebP, HEIC/HEIF, TIFF.",
        )

    # 3. JPEG
    if header.startswith(b"\xff\xd8\xff"):
        return DetectedType("jpeg", "image/jpeg", "JPEG Image")

    # 4. PNG
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return DetectedType("png", "image/png", "Portable Network Graphics")

    # 5. TIFF (Little-Endian 'II*\0' or Big-Endian 'MM\0*')
    if header.startswith(b"II\x2a\x00") or header.startswith(b"MM\x00\x2a"):
        return DetectedType("tiff", "image/tiff", "TIFF Image")

    # 6. RIFF Containers (WebP, AVI, WAV)
    if header.startswith(b"RIFF") and len(header) >= 12:
        riff_type = header[8:12]
        if riff_type == b"WEBP":
            return DetectedType("webp", "image/webp", "WebP Image")
        if riff_type == b"AVI ":
            return DetectedType("avi", "video/x-msvideo", "AVI Video Container")
        if riff_type == b"WAVE":
            return DetectedType("wav", "audio/wav", "Waveform Audio")

    # 7. ISO Base Media File Format (ftyp box: MP4, MOV, M4V, M4A, HEIC, AVIF, 3GP)
    if len(header) >= 12 and header[4:8] == b"ftyp":
        major_brand, compatible = _parse_ftyp_brands(header)
        all_brands = [major_brand] + compatible

        # Check AVIF first (AVIF uses mif1 as a compatible brand too)
        avif_brands = {"avif", "avis"}
        if any(b.strip().lower() in avif_brands for b in all_brands):
            return DetectedType("avif", "image/avif", "AV1 Image File")

        # Check HEIC / HEIF (CRITICAL: must not classify as MP4)
        heic_brands = {"heic", "heix", "heim", "heis", "hevc", "mif1", "msf1"}
        if any(b.strip().lower() in heic_brands for b in all_brands):
            return DetectedType("heic", "image/heic", "HEIC / HEIF Image Container")

        # Check QuickTime MOV
        if major_brand == "qt  ":
            return DetectedType("mov", "video/quicktime", "QuickTime Video")

        # Check M4A Audio
        if major_brand in ("M4A ", "M4B ", "F4A ", "F4B "):
            return DetectedType("m4a", "audio/mp4", "M4A Audio Container")

        # Check M4V Video
        if major_brand in ("M4V ", "M4VH"):
            return DetectedType("m4v", "video/x-m4v", "M4V Video Container")

        # Check MP4
        mp4_brands = {"isom", "iso2", "mp41", "mp42", "dash", "avc1", "face"}
        if any(b.strip().lower() in mp4_brands for b in all_brands):
            return DetectedType("mp4", "video/mp4", "MP4 Video Container")

        # Unknown ftyp brand: reject, do not default to MP4
        raise FileTypeError(
            f"Unsupported ISO-BMFF / ftyp brand '{major_brand.strip()}'.",
            code="UNSUPPORTED_TYPE",
            hint="Supported video/audio: MP4, MOV, M4V, MKV, WebM, AVI, MP3, M4A, WAV, FLAC, OGG.",
        )

    # 8. Matroska / WebM (EBML header \x1a\x45\xdf\xa3)
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        doctype = _detect_ebml_doctype(header)
        if doctype == "webm":
            return DetectedType("webm", "video/webm", "WebM Video")
        return DetectedType("mkv", "video/x-matroska", "Matroska Video Container")

    # 9. PDF
    if b"%PDF-" in header[:1024]:
        return DetectedType("pdf", "application/pdf", "PDF Document")

    # 10. Office Open XML (ZIP archive PK\x03\x04)
    if header.startswith(b"PK\x03\x04"):
        if full_bytes:
            norm_type, mime = _validate_and_classify_ooxml(full_bytes)
            return DetectedType(norm_type, mime, f"Office Open XML ({norm_type.upper()})")
        # If full_bytes not supplied, inspect filename extension as initial hint
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext in ("docx", "xlsx", "pptx"):
            return DetectedType(ext, f"application/vnd.openxmlformats-{ext}", f"Office {ext.upper()}")
        raise FileTypeError(
            "Generic ZIP archive is not supported. Only DOCX, XLSX, and PPTX are supported.",
            code="UNSUPPORTED_TYPE",
        )

    # 11. Audio formats
    if header.startswith(b"fLaC"):
        return DetectedType("flac", "audio/flac", "FLAC Lossless Audio")

    if header.startswith(b"OggS"):
        return DetectedType("ogg", "audio/ogg", "Ogg Vorbis Audio")

    # MP3 (ID3v2 tag or MPEG frame sync)
    if header.startswith(b"ID3") or (
        len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0
    ):
        return DetectedType("mp3", "audio/mpeg", "MP3 Audio")

    # If format doesn't match any supported binary signature
    ext = Path(filename).suffix.lower()
    if ext:
        raise FileTypeError(
            f"File content does not match extension '{ext}'.",
            code="TYPE_MISMATCH",
            hint="Ensure the file is not corrupted or renamed from an unsupported format.",
        )

    raise FileTypeError(
        "Unsupported or unrecognized binary file format.",
        code="UNSUPPORTED_TYPE",
        hint="Supported formats: MP4, MOV, M4V, MKV, WebM, AVI, JPEG, PNG, WebP, HEIC, TIFF, PDF, DOCX, XLSX, PPTX, MP3, M4A, FLAC, WAV, OGG.",
    )
