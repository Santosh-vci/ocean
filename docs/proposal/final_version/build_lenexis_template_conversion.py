from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import posixpath
import xml.etree.ElementTree as ET


BASE_DIR = Path(__file__).resolve().parent
LENEXIS_DOCX = BASE_DIR / "Lenexis Foodworks - Vector's proposal for preparing solution blueprint and implementation in operations and supply chain - 24092024.docx"
ABL_DOCX = BASE_DIR / "ABL_Operational_Blueprinting_Application_Build_final_timelines_draft.docx"

TEMPLATE_DOTX = BASE_DIR / "Lenexis_Foodworks_Vector_Proposal_Template.dotx"
CONVERTED_DOCX = BASE_DIR / "ABL_Operational_Blueprinting_Application_Build_final_timelines_draft_converted_from_Lenexis_template.docx"

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

DOC_MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
TEMPLATE_MAIN_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
ATTACHED_TEMPLATE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/attachedTemplate"

ET.register_namespace("", CONTENT_TYPES_NS)
ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)


def parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def copy_docx_as_dotx_template(src: Path, dest: Path) -> None:
    with ZipFile(src, "r") as zin, ZipFile(dest, "w", ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "[Content_Types].xml":
                root = parse_xml(data)
                changed = False
                for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
                    if override.attrib.get("PartName") == "/word/document.xml":
                        override.set("ContentType", TEMPLATE_MAIN_CT)
                        changed = True
                        break
                if not changed:
                    raise RuntimeError("Could not find /word/document.xml content type in Lenexis DOCX")
                data = xml_bytes(root)
            zout.writestr(info, data)


def existing_relationship_ids(root: ET.Element) -> set[str]:
    ids = set()
    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
        rel_id = rel.attrib.get("Id")
        if rel_id:
            ids.add(rel_id)
    return ids


def next_rel_id(root: ET.Element) -> str:
    ids = existing_relationship_ids(root)
    index = 1
    while f"rId{index}" in ids:
        index += 1
    return f"rId{index}"


def upsert_attached_template_relationship(existing_data: bytes | None, target: str) -> tuple[bytes, str]:
    if existing_data:
        root = parse_xml(existing_data)
    else:
        root = ET.Element(f"{{{REL_NS}}}Relationships")

    attached = None
    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
        if rel.attrib.get("Type") == ATTACHED_TEMPLATE_REL:
            attached = rel
            break

    if attached is None:
        rel_id = next_rel_id(root)
        attached = ET.SubElement(root, f"{{{REL_NS}}}Relationship")
        attached.set("Id", rel_id)
        attached.set("Type", ATTACHED_TEMPLATE_REL)
    else:
        rel_id = attached.attrib["Id"]

    attached.set("Target", target)
    attached.set("TargetMode", "External")
    return xml_bytes(root), rel_id


def upsert_child(root: ET.Element, tag: str) -> ET.Element:
    existing = root.find(tag)
    if existing is not None:
        return existing
    child = ET.Element(tag)
    root.insert(0, child)
    return child


def attach_template_in_settings(existing_data: bytes, rel_id: str) -> bytes:
    root = parse_xml(existing_data)

    attached = upsert_child(root, f"{{{W_NS}}}attachedTemplate")
    attached.set(f"{{{R_NS}}}id", rel_id)

    update_styles = upsert_child(root, f"{{{W_NS}}}updateStyles")
    update_styles.set(f"{{{W_NS}}}val", "true")

    return xml_bytes(root)


def convert_abl_with_template(src: Path, template: Path, dest: Path) -> None:
    rels_path = "word/_rels/settings.xml.rels"
    settings_path = "word/settings.xml"
    relative_template_target = posixpath.basename(template.name)

    with ZipFile(src, "r") as zin:
        rels_data = zin.read(rels_path) if rels_path in zin.namelist() else None
        new_rels_data, rel_id = upsert_attached_template_relationship(rels_data, relative_template_target)
        settings_data = attach_template_in_settings(zin.read(settings_path), rel_id)

        with ZipFile(dest, "w", ZIP_DEFLATED) as zout:
            wrote_rels = False
            for info in zin.infolist():
                if info.filename == rels_path:
                    zout.writestr(info, new_rels_data)
                    wrote_rels = True
                elif info.filename == settings_path:
                    zout.writestr(info, settings_data)
                else:
                    zout.writestr(info, zin.read(info.filename))
            if not wrote_rels:
                zout.writestr(rels_path, new_rels_data)


def verify_template(dest: Path) -> None:
    with ZipFile(dest, "r") as z:
        root = parse_xml(z.read("[Content_Types].xml"))
        ct = None
        for override in root.findall(f"{{{CONTENT_TYPES_NS}}}Override"):
            if override.attrib.get("PartName") == "/word/document.xml":
                ct = override.attrib.get("ContentType")
                break
        if ct != TEMPLATE_MAIN_CT:
            raise RuntimeError(f"Template content type was not set correctly: {ct}")


def verify_content_preserved(src: Path, dest: Path) -> dict[str, int]:
    allowed_changed = {"word/settings.xml", "word/_rels/settings.xml.rels"}
    with ZipFile(src, "r") as src_zip, ZipFile(dest, "r") as dest_zip:
        src_names = set(src_zip.namelist())
        dest_names = set(dest_zip.namelist())
        extra = dest_names - src_names
        missing = src_names - dest_names
        if extra - allowed_changed:
            raise RuntimeError(f"Unexpected extra package parts: {sorted(extra - allowed_changed)}")
        if missing:
            raise RuntimeError(f"Missing package parts: {sorted(missing)}")

        unchanged = 0
        changed = 0
        for name in sorted(src_names):
            if name in allowed_changed:
                changed += 1
                continue
            if src_zip.read(name) != dest_zip.read(name):
                raise RuntimeError(f"Content package part changed unexpectedly: {name}")
            unchanged += 1

        media_count = len([name for name in src_names if name.startswith("word/media/")])
        return {
            "unchanged_parts": unchanged,
            "expected_changed_parts": changed + len(extra & allowed_changed),
            "media_parts": media_count,
        }


def main() -> None:
    for path in (LENEXIS_DOCX, ABL_DOCX):
        if not path.exists():
            raise FileNotFoundError(path)

    copy_docx_as_dotx_template(LENEXIS_DOCX, TEMPLATE_DOTX)
    verify_template(TEMPLATE_DOTX)

    convert_abl_with_template(ABL_DOCX, TEMPLATE_DOTX, CONVERTED_DOCX)
    result = verify_content_preserved(ABL_DOCX, CONVERTED_DOCX)

    print(f"Template: {TEMPLATE_DOTX}")
    print(f"Converted DOCX: {CONVERTED_DOCX}")
    print(f"Unchanged package parts: {result['unchanged_parts']}")
    print(f"Expected settings/template-link changes: {result['expected_changed_parts']}")
    print(f"Media parts preserved: {result['media_parts']}")


if __name__ == "__main__":
    main()
