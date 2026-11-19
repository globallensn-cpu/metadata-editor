"""Integration tests for all format pipelines: Audio, Office DOCX, PDF, Image."""

import zipfile
from pathlib import Path

from apps.api.src.schemas.schemas import RemovalOptions
from apps.worker.src.engine.pipelines.audio import clean_audio
from apps.worker.src.engine.pipelines.image import clean_image
from apps.worker.src.engine.pipelines.office import clean_office
from apps.worker.src.engine.pipelines.pdf import clean_pdf, scan_raw_bytes_for_string
from apps.worker.src.engine.verify import extract_unified_metadata

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def test_audio_mp3_cleaning(tmp_path: Path):
    in_mp3 = FIXTURES_DIR / "sample_test.mp3"
    assert in_mp3.exists()

    out_mp3 = tmp_path / "cleaned.mp3"
    opts = RemovalOptions()

    success, msg = clean_audio(in_mp3, out_mp3, "mp3", opts)
    assert success is True, msg
    assert out_mp3.exists() and out_mp3.stat().st_size > 0

    # Verify ID3 metadata removed
    meta_after = extract_unified_metadata(out_mp3)
    assert "ID3:Artist" not in meta_after
    assert "ID3:Title" not in meta_after


def test_office_docx_cleaning(tmp_path: Path):
    in_docx = FIXTURES_DIR / "sample_test.docx"
    assert in_docx.exists()

    out_docx = tmp_path / "cleaned.docx"
    opts = RemovalOptions(strip_rsid=True)

    success, msg = clean_office(in_docx, out_docx, "docx", opts)
    assert success is True, msg
    assert out_docx.exists()

    # Inspect cleaned DOCX package
    with zipfile.ZipFile(out_docx, "r") as zf:
        # Check core.xml
        core_xml = zf.read("docProps/core.xml").decode("utf-8")
        assert "John Doe" not in core_xml
        assert "Jane Doe" not in core_xml

        # Check app.xml
        app_xml = zf.read("docProps/app.xml").decode("utf-8")
        assert "MegaCorp" not in app_xml

        # Check word/document.xml rsid strip
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "00AABBCC" not in doc_xml
        assert "Confidential Proposal" in doc_xml


def test_pdf_cleaning_and_unrecoverable_strings(tmp_path: Path):
    in_pdf = FIXTURES_DIR / "sample_test.pdf"
    assert in_pdf.exists()

    # Verify original has Secret Informant
    assert scan_raw_bytes_for_string(in_pdf, "Secret Informant") is True

    out_pdf = tmp_path / "cleaned.pdf"
    opts = RemovalOptions()

    success, msg, warnings = clean_pdf(in_pdf, out_pdf, opts)
    assert success is True, msg
    assert out_pdf.exists()

    # Verify author is not recoverable in raw bytes
    has_author = scan_raw_bytes_for_string(out_pdf, "Secret Informant")
    assert has_author is False, "Original author string must not be recoverable from cleaned PDF raw bytes"


def test_image_jpeg_cleaning(tmp_path: Path):
    in_jpg = FIXTURES_DIR / "sample_test.jpg"
    assert in_jpg.exists()

    out_jpg = tmp_path / "cleaned.jpg"
    opts = RemovalOptions()

    success, msg = clean_image(in_jpg, out_jpg, "jpeg", opts)
    assert success is True, msg
    assert out_jpg.exists() and out_jpg.stat().st_size > 0
