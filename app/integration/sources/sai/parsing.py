from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from xml.etree.ElementTree import ParseError

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.integration.sources.nmvs.parsing import ExtractedDataset
from app.integration.sources.sai.client import MAX_ZIP_BYTES, SAIError

NAMESPACE = "http://sai.refdata.ch"
TARGETS = (
    ("SAI-Praeparate.XML", "SAI_PRAEPARATE", "PRAEPARAT"),
    ("SAI-Packungen.XML", "SAI_PACKUNGEN", "PACKUNG"),
    ("SAI-ATC-Codes.XML", "SAI_ATC", "ATC"),
    ("SAI-Adressen.XML", "SAI_ADRESSEN", "ADRESSE"),
)


@dataclass(frozen=True)
class ParsedSAI:
    file_metadata: dict[str, str]
    datasets: tuple[ExtractedDataset, ...]


def parse_sai(content: bytes) -> ParsedSAI:
    if len(content) > MAX_ZIP_BYTES:
        raise SAIError("SAI ZIP exceeds size limit.")
    datasets, metadata = [], {"delivery_mode": "full"}
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if (
                len(members) > 100
                or sum(m.file_size for m in members) > 512 * 1024 * 1024
            ):
                raise SAIError("SAI archive exceeds extraction limits.")
            for order, (filename, root_name, row_name) in enumerate(TARGETS, 1):
                matches = [
                    m
                    for m in members
                    if PurePosixPath(m.filename).name.lower() == filename.lower()
                ]
                if len(matches) != 1:
                    raise SAIError(
                        "SAI archive has missing or duplicate required XML members."
                    )
                member = matches[0]
                if member.file_size > 64 * 1024 * 1024 or member.flag_bits & 1:
                    raise SAIError("Unsupported SAI XML member.")
                root = ET.fromstring(
                    archive.read(member),
                    forbid_dtd=True,
                    forbid_entities=True,
                    forbid_external=True,
                )
                if (
                    root.tag != f"{{{NAMESPACE}}}{root_name}"
                    or root.attrib.get("schemaVersion") != "3.2"
                ):
                    raise SAIError(
                        "Unsupported SAI XML root, namespace or schema version."
                    )
                headers, rows = [], []
                for element in root:
                    if element.tag != f"{{{NAMESPACE}}}{row_name}" or element.attrib:
                        raise SAIError("Unexpected SAI row structure.")
                    row = {}
                    for child in element:
                        if (
                            not child.tag.startswith(f"{{{NAMESPACE}}}")
                            or len(child)
                            or child.attrib
                        ):
                            raise SAIError("Unsupported SAI XML field structure.")
                        name = child.tag.split("}", 1)[1]
                        if name in row:
                            raise SAIError("Duplicate SAI XML field.")
                        row[name] = child.text if child.text is not None else ""
                        if name not in headers:
                            headers.append(name)
                    if not row:
                        raise SAIError("Empty SAI row.")
                    rows.append(row)
                if not rows:
                    raise SAIError("Required SAI dataset is empty.")
                metadata[filename] = member.filename
                metadata[f"{filename}:schemaVersion"] = "3.2"
                datasets.append(
                    ExtractedDataset(root_name, order, tuple(headers), tuple(rows))
                )
    except (
        zipfile.BadZipFile,
        DefusedXmlException,
        ParseError,
        RuntimeError,
        OSError,
        NotImplementedError,
    ):
        raise SAIError("SAI ZIP or XML could not be parsed safely.") from None
    return ParsedSAI(metadata, tuple(datasets))


def normalize_gtin14(value: str | None) -> str | None:
    """Derived identifier only; never modify source values in staging."""
    if value is None or not value.strip():
        return None
    code = value.strip()
    if len(code) not in (8, 12, 13, 14) or not code.isascii() or not code.isdigit():
        raise SAIError("Invalid GTIN format.")
    if (
        sum(int(c) * (3 if i % 2 == 0 else 1) for i, c in enumerate(code[-2::-1]))
        + int(code[-1])
    ) % 10:
        raise SAIError("Invalid GTIN check digit.")
    return code.zfill(14)
