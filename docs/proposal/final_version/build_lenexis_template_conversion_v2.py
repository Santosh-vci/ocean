from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import re
import xml.etree.ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent
LENEXIS_DOCX = BASE_DIR / "Lenexis Foodworks - Vector's proposal for preparing solution blueprint and implementation in operations and supply chain - 24092024.docx"
ABL_DOCX = BASE_DIR / "ABL_Operational_Blueprinting_Application_Build_final_timelines_draft.docx"

CLEAN_TEMPLATE_DOTX = BASE_DIR / "Lenexis_Foodworks_Vector_Proposal_Template_clean.dotx"
CONVERTED_DOCX = BASE_DIR / "ABL_Operational_Blueprinting_Application_Build_final_timelines_draft_converted_from_Lenexis_template_v2.docx"

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
TEMPLATE_MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
ATTACHED_TEMPLATE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate"

ET.register_namespace("", CONTENT_TYPES_NS)
ET.register_namespace("", REL_NS)


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_content_type_to_template(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
        if override.attrib.get("PartName") == "/word/document.xml":
            override.set("ContentType", TEMPLATE_MAIN_CT)
            return xml_bytes(root)
    raise RuntimeError("Could not find /word/document.xml content type")


def relationship_ids(root: ET.Element) -> set[str]:
    return {rel.attrib["Id"] for rel in root.findall(f"{{{REL_NS}}}Relationship") if "Id" in rel.attrib}


def next_rid(root: ET.Element) -> str:
    ids = relationship_ids(root)
    index = 1
    while f"rId{index}" in ids:
        index += 1
    return f"rId{index}"


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


def create_attached_template_rels(existing_data: bytes | None, target: str) -> tuple[bytes, str]:
    if existing_data:
        root = ET.fromstring(existing_data)
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


def remove_attached_template_from_settings_raw(data: bytes) -> bytes:
    text = data.decode("utf-8-sig")
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*/>", "", text)
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*>.*?</w:attachedTemplate>", "", text, flags=re.S)
    return text.encode("utf-8")


def insert_attached_template_in_settings_raw(data: bytes, rid: str) -> bytes:
    text = data.decode("utf-8-sig")
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*/>", "", text)
    text = re.sub(r"\s*<w:attachedTemplate\b[^>]*>.*?</w:attachedTemplate>", "", text, flags=re.S)
    attached = f'<w:attachedTemplate r:id="{rid}"/>'

    # Word's own Lenexis settings place attachedTemplate after hideGrammaticalErrors
    # and before defaultTabStop. Preserve the rest of settings.xml byte structure.
    markers = [
        r"(<w:hideGrammaticalErrors\s*/>)",
        r"(<w:hideSpellingErrors\s*/>)",
        r"(<w:zoom\b[^>]*/>)",
    ]
    for pattern in markers:
        match = re.search(pattern, text)
        if match:
            insert_at = match.end()
            text = text[:insert_at] + attached + text[insert_at:]
            return text.encode("utf-8")

    default_tab = re.search(r"<w:defaultTabStop\b", text)
    if default_tab:
        text = text[: default_tab.start()] + attached + text[default_tab.start() :]
        return text.encode("utf-8")

    end_settings = text.rfind("</w:settings>")
    if end_settings < 0:
        raise RuntimeError("Could not find </w:settings>")
    text = text[:end_settings] + attached + text[end_settings:]
    return text.encode("utf-8")


def build_clean_template() -> None:
    rels_path = "word/_rels/settings.xml.rels"
    settings_path = "word/settings.xml"

    with ZipFile(LENEXIS_DOCX, "r") as zin, ZipFile(CLEAN_TEMPLATE_DOTX, "w", ZIP_DEFLATED) as zout:
        cleaned_rels = None
        if rels_path in zin.namelist():
            cleaned_rels = remove_attached_template_from_rels(zin.read(rels_path))

        for info in zin.infolist():
            name = info.filename
            data = zin.read(name)
            if name == "[Content_Types].xml":
                data = update_content_type_to_template(data)
            elif name == settings_path:
                data = remove_attached_template_from_settings_raw(data)
            elif name == rels_path:
                if cleaned_rels is None:
                    continue
                data = cleaned_rels
            zout.writestr(info, data)


def build_converted_docx() -> None:
    rels_path = "word/_rels/settings.xml.rels"
    settings_path = "word/settings.xml"
    target = CLEAN_TEMPLATE_DOTX.name

    with ZipFile(ABL_DOCX, "r") as zin:
        new_rels, rid = create_attached_template_rels(
            zin.read(rels_path) if rels_path in zin.namelist() else None,
            target,
        )
        new_settings = insert_attached_template_in_settings_raw(zin.read(settings_path), rid)

        with ZipFile(CONVERTED_DOCX, "w", ZIP_DEFLATED) as zout:
            wrote_rels = False
            for info in zin.infolist():
                name = info.filename
                if name == rels_path:
                    zout.writestr(info, new_rels)
                    wrote_rels = True
                elif name == settings_path:
                    zout.writestr(info, new_settings)
                else:
                    zout.writestr(info, zin.read(name))
            if not wrote_rels:
                zout.writestr(rels_path, new_rels)


def verify_packages() -> None:
    for path in (CLEAN_TEMPLATE_DOTX, CONVERTED_DOCX):
        with ZipFile(path, "r") as z:
            bad = z.testzip()
            if bad:
                raise RuntimeError(f"{path.name} has bad ZIP entry: {bad}")
            for name in z.namelist():
                if name.endswith(".xml"):
                    ET.fromstring(z.read(name))

    with ZipFile(CLEAN_TEMPLATE_DOTX, "r") as z:
        root = ET.fromstring(z.read("[Content_Types].xml"))
        content_type = None
        for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
            if override.attrib.get("PartName") == "/word/document.xml":
                content_type = override.attrib.get("ContentType")
        if content_type != TEMPLATE_MAIN_CT:
            raise RuntimeError(f"Template content type is wrong: {content_type}")

    with ZipFile(CONVERTED_DOCX, "r") as z:
        settings = z.read("word/settings.xml").decode("utf-8", errors="replace")
        if "xmlns:w=" not in settings or "xmlns:r=" not in settings:
            raise RuntimeError("Converted settings.xml did not preserve Word namespace declarations")
        if "<w:attachedTemplate" not in settings:
            raise RuntimeError("Converted document has no attached template setting")
        rels = z.read("word/_rels/settings.xml.rels").decode("utf-8", errors="replace")
        if CLEAN_TEMPLATE_DOTX.name not in rels:
            raise RuntimeError("Converted document is not linked to the clean template")


def main() -> None:
    for path in (LENEXIS_DOCX, ABL_DOCX):
        if not path.exists():
            raise FileNotFoundError(path)
    build_clean_template()
    build_converted_docx()
    verify_packages()
    print(f"Clean template: {CLEAN_TEMPLATE_DOTX}")
    print(f"Converted DOCX v2: {CONVERTED_DOCX}")


if __name__ == "__main__":
    main()
