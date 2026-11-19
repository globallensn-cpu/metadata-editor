"""Reaboard Office Document (OOXML) Sanitization Pipeline.

Sanitizes DOCX, XLSX, and PPTX packages by parsing XML properties, stripping author
identities, revision timestamps, company names, and Word rsid tracking attributes.
Repacks deterministically with fixed timestamps and validates package integrity.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from apps.api.src.schemas.schemas import RemovalOptions

DETERMINISTIC_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def clean_office_document(
    input_path: Path,
    output_path: Path,
    format_hint_or_options: Any = None,
    options: RemovalOptions | None = None,
) -> tuple[bool, str]:
    """Sanitize and deterministically repack an Office Open XML document."""
    if isinstance(format_hint_or_options, RemovalOptions):
        opts = format_hint_or_options
    else:
        opts = options or RemovalOptions()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(input_path, "r") as src_zip:
            cleaned_entries: dict[str, bytes] = {}

            for item in src_zip.infolist():
                name = item.filename
                content = src_zip.read(name)

                # 1. Sanitize Core Properties (docProps/core.xml)
                if name.lower() == "docProps/core.xml".lower():
                    content = _sanitize_core_properties(content, opts)

                # 2. Sanitize App Properties (docProps/app.xml)
                elif name.lower() == "docProps/app.xml".lower():
                    content = _sanitize_app_properties(content)

                # 3. Custom Properties (docProps/custom.xml)
                elif name.lower() == "docProps/custom.xml".lower():
                    content = _sanitize_custom_properties(content)

                # 4. Word XML rsid tracking attributes
                elif name.startswith("word/") and name.endswith(".xml"):
                    content = _strip_word_rsid_attributes(content)

                cleaned_entries[name] = content

            # Deterministic repack: [Content_Types].xml first, then sorted names
            names_ordered = []
            if "[Content_Types].xml" in cleaned_entries:
                names_ordered.append("[Content_Types].xml")
            for k in sorted(cleaned_entries.keys()):
                if k != "[Content_Types].xml":
                    names_ordered.append(k)

            with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as dst_zip:
                for name in names_ordered:
                    zinfo = zipfile.ZipInfo(name, date_time=DETERMINISTIC_TIMESTAMP)
                    zinfo.compress_type = zipfile.ZIP_DEFLATED
                    dst_zip.writestr(zinfo, cleaned_entries[name])

        # Validate that package re-opens cleanly
        with zipfile.ZipFile(output_path, "r") as test_zip:
            ct = test_zip.read("[Content_Types].xml")
            ET.fromstring(ct)

        return True, "Office document metadata and revision tracking sanitized successfully"

    except Exception as e:
        return False, f"Office document repack failed: {str(e)}"


def _sanitize_core_properties(xml_bytes: bytes, opts: RemovalOptions) -> bytes:
    """Clear dc:creator, cp:lastModifiedBy, dcterms:created, and dcterms:modified."""
    text = xml_bytes.decode("utf-8", errors="replace")

    if opts.strip_office_authors:
        text = re.sub(r"<dc:creator>[^<]*</dc:creator>", "<dc:creator></dc:creator>", text)
        text = re.sub(
            r"<cp:lastModifiedBy>[^<]*</cp:lastModifiedBy>",
            "<cp:lastModifiedBy></cp:lastModifiedBy>",
            text,
        )

    # Blank timestamps and revisions
    text = re.sub(r"<dcterms:created[^>]*>[^<]*</dcterms:created>", "", text)
    text = re.sub(r"<dcterms:modified[^>]*>[^<]*</dcterms:modified>", "", text)
    text = re.sub(r"<cp:revision>[^<]*</cp:revision>", "<cp:revision>1</cp:revision>", text)

    return text.encode("utf-8")


def _sanitize_app_properties(xml_bytes: bytes) -> bytes:
    """Clear Company, Manager, HyperlinkBase, and Template metadata."""
    text = xml_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"<Company>[^<]*</Company>", "<Company></Company>", text)
    text = re.sub(r"<Manager>[^<]*</Manager>", "<Manager></Manager>", text)
    text = re.sub(r"<Template>[^<]*</Template>", "<Template></Template>", text)
    text = re.sub(r"<HyperlinkBase>[^<]*</HyperlinkBase>", "", text)
    return text.encode("utf-8")


def _sanitize_custom_properties(xml_bytes: bytes) -> bytes:
    """Clear custom document property values."""
    text = xml_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"<property[^>]*>.*?</property>", "", text, flags=re.DOTALL)
    return text.encode("utf-8")


def _strip_word_rsid_attributes(xml_bytes: bytes) -> bytes:
    """Remove revision save IDs (rsid) from Word document XML tags."""
    text = xml_bytes.decode("utf-8", errors="replace")
    text = re.sub(r'\s+w:rsid[A-Za-z0-9]+="[0-9A-Fa-f]+"', "", text)
    return text.encode("utf-8")


# Alias for unified pipeline naming
clean_office = clean_office_document

