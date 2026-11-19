"""Unit tests for File Type Detection & Security Bomb Validation."""

import io
import struct
import zipfile

import pytest

from apps.api.src.core.filetype import (
    FileTypeError,
    _validate_and_classify_ooxml,
    detect_file_type,
)


def make_ftyp(major_brand: str, compatible: list[str]) -> bytes:
    """Helper to craft an ISO Base Media File Format ftyp box."""
    data = major_brand.encode("latin1") + b"".join(b.encode("latin1") for b in compatible)
    box_len = 8 + len(data)
    return struct.pack(">I", box_len) + b"ftyp" + data + (b"\x00" * 100)


def test_detect_mp4_brands():
    header = make_ftyp("isom", ["mp42", "avc1"])
    det = detect_file_type(header, "test.mp4")
    assert det.normalized_type == "mp4"
    assert det.mime_type == "video/mp4"


def test_detect_mov_quicktime():
    header = make_ftyp("qt  ", ["qt  "])
    det = detect_file_type(header, "test.mov")
    assert det.normalized_type == "mov"
    assert det.mime_type == "video/quicktime"


def test_detect_heic_never_classified_as_mp4():
    # HEIC brand must never map to MP4
    header = make_ftyp("heic", ["mif1", "heic"])
    det = detect_file_type(header, "iphone_photo.heic")
    assert det.normalized_type == "heic"
    assert det.mime_type == "image/heic"

    header_mif1 = make_ftyp("mif1", ["heix", "msf1"])
    det_mif1 = detect_file_type(header_mif1, "photo.heif")
    assert det_mif1.normalized_type == "heic"


def test_detect_avif():
    header = make_ftyp("avif", ["avis", "mif1"])
    det = detect_file_type(header, "test.avif")
    assert det.normalized_type == "avif"


def test_reject_unknown_ftyp_brand():
    header = make_ftyp("xyz9", ["none"])
    with pytest.raises(FileTypeError) as exc:
        detect_file_type(header, "test.mp4")
    assert exc.value.code == "UNSUPPORTED_TYPE"


def test_detect_tiff_endianness():
    # Little-endian II*\0
    le = b"II\x2a\x00" + (b"\x00" * 100)
    assert detect_file_type(le, "test.tiff").normalized_type == "tiff"

    # Big-endian MM\0*
    be = b"MM\x00\x2a" + (b"\x00" * 100)
    assert detect_file_type(be, "test.tif").normalized_type == "tiff"


def test_reject_gif():
    header = b"GIF89a" + (b"\x00" * 100)
    with pytest.raises(FileTypeError) as exc:
        detect_file_type(header, "test.gif")
    assert exc.value.code == "UNSUPPORTED_TYPE"
    assert "out of scope" in exc.value.message.lower()


def test_detect_ebml_mkv_and_webm():
    # EBML header with webm doctype
    ebml_webm = b"\x1a\x45\xdf\xa3" + (b"\x00" * 10) + b"webm" + (b"\x00" * 50)
    assert detect_file_type(ebml_webm, "test.webm").normalized_type == "webm"

    # EBML header with matroska doctype
    ebml_mkv = b"\x1a\x45\xdf\xa3" + (b"\x00" * 10) + b"matroska" + (b"\x00" * 50)
    assert detect_file_type(ebml_mkv, "test.mkv").normalized_type == "mkv"


def test_detect_pdf():
    pdf_hdr = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + (b"\x00" * 100)
    assert detect_file_type(pdf_hdr, "document.pdf").normalized_type == "pdf"


def test_detect_ooxml_docx_from_content():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<Types><Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("word/document.xml", "<w:document/>")
    data = buf.getvalue()

    det = detect_file_type(data[:1024], "doc.docx", full_bytes=data)
    assert det.normalized_type == "docx"


def test_detect_ooxml_xlsx_from_content():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<Types><Override ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        z.writestr("xl/workbook.xml", "<workbook/>")
    data = buf.getvalue()

    det = detect_file_type(data[:1024], "sheet.xlsx", full_bytes=data)
    assert det.normalized_type == "xlsx"


def test_ooxml_zip_bomb_entry_limit():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(501):
            z.writestr(f"file_{i}.txt", "test")
    data = buf.getvalue()

    with pytest.raises(FileTypeError) as exc:
        _validate_and_classify_ooxml(data)
    assert exc.value.code == "FILE_TOO_LARGE"
    assert "entry limit" in exc.value.message


def test_hostile_executables_and_scripts_rejected():
    # Windows PE executable
    with pytest.raises(FileTypeError) as exc:
        detect_file_type(b"MZ\x90\x00" + (b"\x00" * 50), "fake.mp4")
    assert exc.value.code == "TYPE_MISMATCH"

    # Linux ELF executable
    with pytest.raises(FileTypeError) as exc:
        detect_file_type(b"\x7fELF\x02\x01\x01\x00" + (b"\x00" * 50), "fake.png")
    assert exc.value.code == "TYPE_MISMATCH"

    # Shell script disguised as video
    with pytest.raises(FileTypeError) as exc:
        detect_file_type(b"#!/bin/bash\nrm -rf /" + (b"\x00" * 50), "script.mp4")
    assert exc.value.code == "TYPE_MISMATCH"
