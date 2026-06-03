from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import re
import xml.etree.ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent
LENEXIS_DOCX = BASE_DIR / "Lenexis Foodworks - Vector's proposal for preparing solution blueprint and implementation in operations and supply chain - 24092024.docx"
ABL_DOCX = BASE_DIR / "ABL_Operational_Blueprinting_Application_Build_final_timelines_draft.docx"

REUSABLE_TEMPLATE = BASE_DIR / "Vector_Reusable_Proposal_Template_from_Lenexis.dotx"
ABL_REBUILT = BASE_DIR / "ABL_Operational_Blueprinting_Application_Build_final_timelines_draft_rebuilt_with_Vector_template.docx"

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
TEMPLATE_MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
ATTACHED_TEMPLATE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate"

ET.register_namespace("", CONTENT_TYPES_NS)
ET.register_namespace("", REL_NS)


STYLE_PARTS_TO_APPLY = {
    "word/styles.xml",
    "word/theme/theme1.xml",
    "word/fontTable.xml",
    "word/webSettings.xml",
}


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def replace_text_preserve_encoding(data: bytes, replacements: dict[str, str]) -> bytes:
    text = data.decode("utf-8-sig")
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("utf-8")


def update_content_type_to_template(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == "/word/document.xml":
            override.set("ContentType", TEMPLATE_MAIN_CT)
            return xml_bytes(root)
    raise RuntimeError("Could not find /word/document.xml override")


def remove_attached_template_from_rels(data: bytes | None) -> bytes | None:
    if not data:
        return None
    root = ET.fromstring(data)
    removed = False
    for rel in list(root.findall(f"{{{REL_NS}}}Relationship")):
        if rel.attrib.get("Type") == ATTACHED_TEMPLATE_REL:
            root.remove(rel)
            removed = True
    if not removed:
        return data
    if len(list(root)) == 0:
        return None
    return xml_bytes(root)


def remove_attached_template_from_settings(data: bytes) -> bytes:
    text = data.decode("utf-8-sig")
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*/>", "", text)
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*>.*?</w:attachedTemplate>", "", text, flags=re.S)
    return text.encode("utf-8")


def add_attached_template_to_settings(data: bytes, rel_id: str) -> bytes:
    text = data.decode("utf-8-sig")
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*/>", "", text)
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*>.*?</w:attachedTemplate>", "", text, flags=re.S)
    attached = f'<w:attachedTemplate r:id="{rel_id}"/>'

    for pattern in [
        r"(<w:hideGrammaticalErrors\s*/>)",
        r"(<w:hideSpellingErrors\s*/>)",
        r"(<w:zoom\b[^>]*/>)",
    ]:
        match = re.search(pattern, text)
        if match:
            return (text[: match.end()] + attached + text[match.end() :]).encode("utf-8")

    match = re.search(r"<w:defaultTabStop\b", text)
    if match:
        return (text[: match.start()] + attached + text[match.start() :]).encode("utf-8")

    end = text.rfind("</w:settings>")
    if end < 0:
        raise RuntimeError("Could not find </w:settings>")
    return (text[:end] + attached + text[end:]).encode("utf-8")


def relationship_ids(root: ET.Element) -> set[str]:
    return {rel.attrib["Id"] for rel in root.findall(f"{{{REL_NS}}}Relationship") if "Id" in rel.attrib}


def next_rid(root: ET.Element) -> str:
    ids = relationship_ids(root)
    index = 1
    while f"rId{index}" in ids:
        index += 1
    return f"rId{index}"


def add_template_relationship(data: bytes | None, target: str) -> tuple[bytes, str]:
    if data:
        root = ET.fromstring(data)
    else:
        root = ET.Element(f"{{{REL_NS}}}Relationships")

    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
        if rel.attrib.get("Type") == ATTACHED_TEMPLATE_REL:
            rel.set("Target", target)
            rel.set("TargetMode", "External")
            return xml_bytes(root), rel.attrib["Id"]

    rid = next_rid(root)
    rel = ET.SubElement(root, f"{{{REL_NS}}}Relationship")
    rel.set("Id", rid)
    rel.set("Type", ATTACHED_TEMPLATE_REL)
    rel.set("Target", target)
    rel.set("TargetMode", "External")
    return xml_bytes(root), rid


def extract_root_open_tag(document_xml: str) -> str:
    match = re.search(r"<w:document\b[^>]*>", document_xml)
    if not match:
        raise RuntimeError("Could not find opening w:document tag")
    return match.group(0)


def extract_last_sectpr(document_xml: str) -> str:
    matches = re.findall(r"<w:sectPr\b.*?</w:sectPr>", document_xml, flags=re.S)
    if not matches:
        raise RuntimeError("Could not find w:sectPr in template source")
    return matches[-1]


def paragraph(text: str, style: str | None = None, bold: bool = False) -> str:
    ppr = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    safe = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return f"<w:p>{ppr}<w:r>{rpr}<w:t>{safe}</w:t></w:r></w:p>"


def build_template_document_xml(source_document_xml: bytes) -> bytes:
    original = source_document_xml.decode("utf-8-sig")
    root_open = extract_root_open_tag(original)
    sect_pr = extract_last_sectpr(original)
    body = "".join(
        [
            paragraph("Proposal Title", "Title"),
            paragraph("Prepared for [Client Name]", "Subtitle"),
            paragraph("Proposal", "Heading1"),
            paragraph("Created by Vector Consulting Group - [Date] [Revision]"),
            paragraph(
                "This document is proprietary to Vector Consulting Group. It should not be disclosed, duplicated, or shared outside the intended recipient organization without consent of Vector Consulting Group."
            ),
            paragraph("Contents", "TOCHeading"),
            paragraph("[Document sections to be inserted here.]"),
        ]
    )
    xml = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n{root_open}<w:body>{body}{sect_pr}</w:body></w:document>'
    return xml.encode("utf-8")


def build_reusable_template() -> None:
    rels_path = "word/_rels/settings.xml.rels"
    with ZipFile(LENEXIS_DOCX, "r") as zin, ZipFile(REUSABLE_TEMPLATE, "w", ZIP_DEFLATED) as zout:
        cleaned_settings_rels = (
            remove_attached_template_from_rels(zin.read(rels_path))
            if rels_path in zin.namelist()
            else None
        )

        for info in zin.infolist():
            name = info.filename
            data = zin.read(name)
            if name == "[Content_Types].xml":
                data = update_content_type_to_template(data)
            elif name == "word/document.xml":
                data = build_template_document_xml(data)
            elif name == "word/settings.xml":
                data = remove_attached_template_from_settings(data)
            elif name == rels_path:
                if cleaned_settings_rels is None:
                    continue
                data = cleaned_settings_rels
            elif name == "word/header1.xml":
                data = replace_text_preserve_encoding(
                    data,
                    {
                        "Lenexis Foodworks": "[Client Name]",
                        "Lenexis": "[Client Name]",
                    },
                )
            elif name.startswith("docProps/"):
                data = replace_text_preserve_encoding(
                    data,
                    {
                        "Lenexis Foodworks": "Client Name",
                        "Lenexis": "Client Name",
                        "Preparation of Solution Blueprint and Implementation for Operations and Supply Chain Excellence": "Proposal Title",
                    },
                )
            zout.writestr(info, data)


def build_abl_rebuilt_doc() -> None:
    settings_rels_path = "word/_rels/settings.xml.rels"
    template_target = REUSABLE_TEMPLATE.name

    with ZipFile(REUSABLE_TEMPLATE, "r") as template_zip:
        template_parts = {part: template_zip.read(part) for part in STYLE_PARTS_TO_APPLY if part in template_zip.namelist()}

    with ZipFile(ABL_DOCX, "r") as zin:
        new_settings_rels, rid = add_template_relationship(
            zin.read(settings_rels_path) if settings_rels_path in zin.namelist() else None,
            template_target,
        )
        new_settings = add_attached_template_to_settings(zin.read("word/settings.xml"), rid)

        with ZipFile(ABL_REBUILT, "w", ZIP_DEFLATED) as zout:
            wrote_settings_rels = False
            for info in zin.infolist():
                name = info.filename
                if name in template_parts:
                    zout.writestr(info, template_parts[name])
                elif name == settings_rels_path:
                    zout.writestr(info, new_settings_rels)
                    wrote_settings_rels = True
                elif name == "word/settings.xml":
                    zout.writestr(info, new_settings)
                else:
                    zout.writestr(info, zin.read(name))
            if not wrote_settings_rels:
                zout.writestr(settings_rels_path, new_settings_rels)


def verify_package(path: Path) -> None:
    with ZipFile(path, "r") as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"{path.name}: bad ZIP entry {bad}")
        for name in z.namelist():
            if name.endswith(".xml"):
                ET.fromstring(z.read(name))


def template_has_no_lenexis_body() -> None:
    with ZipFile(REUSABLE_TEMPLATE, "r") as z:
        body = z.read("word/document.xml").decode("utf-8", errors="replace")
        header = z.read("word/header1.xml").decode("utf-8", errors="replace")
        if "Lenexis" in body or "Lenexis" in header:
            raise RuntimeError("Reusable template still contains Lenexis-specific text")
        if "Proposal Title" not in body or "[Client Name]" not in body:
            raise RuntimeError("Reusable template placeholders were not created")


def verify_abl_content_preserved() -> dict[str, int]:
    expected_changed = {
        "word/styles.xml",
        "word/theme/theme1.xml",
        "word/fontTable.xml",
        "word/webSettings.xml",
        "word/settings.xml",
        "word/_rels/settings.xml.rels",
    }
    with ZipFile(ABL_DOCX, "r") as src, ZipFile(ABL_REBUILT, "r") as dest:
        src_names = set(src.namelist())
        dest_names = set(dest.namelist())
        extra = dest_names - src_names
        missing = src_names - dest_names
        if extra - {"word/_rels/settings.xml.rels"}:
            raise RuntimeError(f"Unexpected extra package parts: {sorted(extra)}")
        if missing:
            raise RuntimeError(f"Missing package parts: {sorted(missing)}")
        unchanged = 0
        for name in src_names:
            if name in expected_changed:
                continue
            if src.read(name) != dest.read(name):
                raise RuntimeError(f"Unexpected content change in {name}")
            unchanged += 1
        return {
            "unchanged_content_parts": unchanged,
            "expected_template_style_parts": len(expected_changed & dest_names),
            "extra_expected_parts": len(extra),
        }


def main() -> None:
    for source in (LENEXIS_DOCX, ABL_DOCX):
        if not source.exists():
            raise FileNotFoundError(source)
    build_reusable_template()
    build_abl_rebuilt_doc()
    verify_package(REUSABLE_TEMPLATE)
    verify_package(ABL_REBUILT)
    template_has_no_lenexis_body()
    preservation = verify_abl_content_preserved()
    print(f"Reusable template: {REUSABLE_TEMPLATE}")
    print(f"ABL rebuilt DOCX: {ABL_REBUILT}")
    print(f"Unchanged ABL content/package parts: {preservation['unchanged_content_parts']}")
    print(f"Expected template/style/settings parts changed: {preservation['expected_template_style_parts']}")
    print(f"Expected added parts: {preservation['extra_expected_parts']}")


if __name__ == "__main__":
    main()
