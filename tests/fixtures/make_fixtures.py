"""Script to generate synthetic test media fixtures with injected metadata."""

import subprocess
import zipfile
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def create_synthetic_mp4():
    """Create a 1-second MP4 with injected GPS and device tags via FFmpeg."""
    out_file = FIXTURE_DIR / "sample_gps.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=1:size=320x240:rate=15",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-metadata", "location=+37.7749-122.4194/",
        "-metadata", "location-eng=+37.7749-122.4194/",
        "-metadata", "model=iPhone 15 Pro",
        "-metadata", "make=Apple",
        "-metadata", "creation_time=2026-11-19T09:00:00.000000Z",
        "-metadata:s:v", "handler_name=Core Media Video",
        str(out_file),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Created synthetic MP4:", out_file)


def create_hostile_file():
    """Create a text script disguised as MP4 to test magic byte rejection."""
    out_file = FIXTURE_DIR / "hostile_script.mp4"
    out_file.write_text("#!/bin/sh\necho 'exploit attempt'\n")
    print("Created hostile script test:", out_file)


def create_synthetic_jpg():
    """Create a 1-pixel or small test JPEG via FFmpeg."""
    out_file = FIXTURE_DIR / "sample_test.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "color=c=blue:s=160x120:d=1",
        "-vframes", "1",
        str(out_file),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Created synthetic JPEG:", out_file)


def create_synthetic_mp3():
    """Create a 1-second MP3 with ID3v2 tags."""
    out_file = FIXTURE_DIR / "sample_test.mp3"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=1",
        "-c:a", "libmp3lame",
        "-metadata", "artist=Secret Artist",
        "-metadata", "title=Secret Track",
        "-metadata", "album=Secret Album",
        "-metadata", "date=2026",
        str(out_file),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Created synthetic MP3:", out_file)


def create_synthetic_docx():
    """Create a minimal valid DOCX file with injected author and rsid attributes."""
    out_file = FIXTURE_DIR / "sample_test.docx"
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        '  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>\n'
        '</Types>'
    )
    core_props = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        '  <dc:creator>John Doe</dc:creator>\n'
        '  <cp:lastModifiedBy>Jane Doe</cp:lastModifiedBy>\n'
        '</cp:coreProperties>'
    )
    app_props = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">\n'
        '  <Company>MegaCorp Inc</Company>\n'
        '</Properties>'
    )
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        '  <w:body>\n'
        '    <w:p w:rsidR="00AABBCC">\n'
        '      <w:r><w:t>Confidential Proposal</w:t></w:r>\n'
        '    </w:p>\n'
        '  </w:body>\n'
        '</w:document>'
    )

    with zipfile.ZipFile(out_file, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("docProps/core.xml", core_props)
        zf.writestr("docProps/app.xml", app_props)
        zf.writestr("word/document.xml", document_xml)

    print("Created synthetic DOCX:", out_file)


def create_synthetic_pdf():
    """Create a minimal valid PDF with author and producer in Info dictionary."""
    out_file = FIXTURE_DIR / "sample_test.pdf"
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>\nendobj\n"
        b"4 0 obj\n<< /Length 20 >>\nstream\nBT /F1 12 Tf ET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Title (Classified Intel) /Author (Secret Informant) /Producer (TestPDF) >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000204 00000 n \n0000000275 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R /Info 5 0 R >>\nstartxref\n370\n%%EOF\n"
    )
    out_file.write_bytes(pdf_bytes)
    print("Created synthetic PDF:", out_file)


if __name__ == "__main__":
    create_synthetic_mp4()
    create_hostile_file()
    create_synthetic_jpg()
    create_synthetic_mp3()
    create_synthetic_docx()
    create_synthetic_pdf()
