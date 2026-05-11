"""Alignment-set discovery and loading helpers."""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

from lxml import etree


def _resources_dir(project_root: Path) -> Path:
    return project_root / "Resources"


def _manifest_dirs(project_root: Path) -> list[Path]:
    return [
        project_root / "Alignments" / "Sets",
        _resources_dir(project_root) / "AlignmentSets",
    ]


def _manifests_dir(project_root: Path) -> Path:
    for directory in _manifest_dirs(project_root):
        if directory.exists():
            return directory
    return _manifest_dirs(project_root)[0]


def list_alignment_sets(project_root: Path | None = None, force_refresh: bool = False) -> list[dict[str, Any]]:
    """Discover alignment sets from classic manifests and collection descriptors."""
    root = (project_root or Path.cwd()).resolve()
    by_id: dict[str, dict[str, Any]] = {}
    for manifests in _manifest_dirs(root):
        if not manifests.exists():
            continue
        for path in sorted(manifests.glob("*.xml")):
            stem = path.stem
            try:
                tree = _load_xml(path)
                el = tree.getroot()
                local = _local_tag(el)
                if local == "tuSetCollection":
                    for row in _expand_collection_descriptor_cached(path, el, root, force_refresh=force_refresh):
                        set_id = str(row.get("id") or "").strip()
                        if not set_id:
                            continue
                        title = str(row.get("title") or "").strip()
                        if set_id not in by_id:
                            by_id[set_id] = {"id": set_id, "title": title}
                    continue
                set_id = (el.get("id") or stem).strip() or stem
                title = (el.get("title") or "").strip()
            except OSError:
                set_id = stem
                title = ""
            except Exception:
                # Unreadable or invalid XML must not hide every other set from discovery.
                continue
            if set_id not in by_id:
                by_id[set_id] = {"id": set_id, "title": title}
    return sorted(by_id.values(), key=lambda r: str(r["id"]).casefold())


def _load_xml(path: Path) -> etree._ElementTree:
    return etree.parse(str(path), etree.XMLParser(remove_blank_text=False, recover=True))


def _collection_cache_path(project_root: Path) -> Path:
    return _resources_dir(project_root) / ".flexalign_set_cache.json"


def _load_collection_cache(project_root: Path) -> dict[str, Any]:
    path = _collection_cache_path(project_root)
    if not path.exists():
        return {"version": 1, "descriptors": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "descriptors": {}}
    if not isinstance(data, dict):
        return {"version": 1, "descriptors": {}}
    if data.get("version") != 1:
        return {"version": 1, "descriptors": {}}
    if not isinstance(data.get("descriptors"), dict):
        data["descriptors"] = {}
    return data


def _save_collection_cache(project_root: Path, cache: dict[str, Any]) -> None:
    path = _collection_cache_path(project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return


def _local_tag(elem: etree._Element) -> str:
    tag = elem.tag
    if not isinstance(tag, str):
        return ""
    if tag.startswith("{"):
        return tag.split("}", 1)[-1]
    return tag


def _extract_doc_title(path: Path) -> str:
    try:
        tree = _load_xml(path)
        root = tree.getroot()
        # Prefer teiHeader/titleStmt/title, then any first title.
        node = root.xpath(
            ".//*[local-name()='titleStmt']/*[local-name()='title'][normalize-space(string())][1]"
        )
        if not node:
            node = root.xpath(".//*[local-name()='title'][normalize-space(string())][1]")
        raw_title = ""
        if node:
            raw_title = " ".join("".join(node[0].itertext()).split()).strip()
        clean = raw_title
        # Normalize common enriched header form:
        #   source.id - Language - Headline
        # Keep only the headline part so UI titles stay concise.
        parts = [p.strip() for p in clean.split(" - ")]
        if len(parts) >= 3 and re.fullmatch(r".+\.\d+", parts[0]):
            clean = " - ".join(parts[2:]).strip()
        if clean.endswith("-"):
            clean = clean[:-1].strip()
        stem = path.stem
        generic_title_patterns = (
            r".+\.\d+\s*",  # source.id
            r".+\.\d+\s*-\s*$",  # source.id -
            r".+\.\d+\s*-\s*[A-Za-z][A-Za-z -]*$",  # source.id - English
        )
        is_generic = (
            not clean
            or clean.casefold() == stem.casefold()
            or any(re.fullmatch(pat, clean) for pat in generic_title_patterns)
        )
        # If header title is empty/generic (e.g. "source.id -" / "source.id - English"), use sentence text.
        if is_generic:
            s_node = root.xpath(".//*[local-name()='s'][1]")
            if s_node:
                s = s_node[0]
                first_txt = (s.get("text") or "").strip()
                if not first_txt:
                    first_txt = " ".join("".join(s.itertext()).split()).strip()
                if first_txt:
                    if len(first_txt) > 120:
                        first_txt = first_txt[:117].rstrip() + "..."
                    return first_txt
        if clean:
            return clean
    except OSError:
        pass
    return path.stem


def _doc_id_from_filename(path: Path) -> str:
    stem = path.stem  # e.g. bbc.381790-eng
    m = re.match(r"^(?P<docid>.+\.\d+)-[A-Za-z0-9-]+$", stem)
    if m:
        return m.group("docid")
    return stem.rsplit("-", 1)[0]


def _load_doclist_titles(project_root: Path) -> dict[str, str]:
    path = _resources_dir(project_root) / "doclist.xml"
    if not path.exists():
        return {}
    try:
        tree = _load_xml(path)
    except OSError:
        return {}
    root = tree.getroot()
    out: dict[str, str] = {}
    for node in root.xpath(".//*[local-name()='doc']"):
        doc_id = (node.get("id") or "").strip()
        if not doc_id:
            continue
        title_node = node.xpath("./*[local-name()='title'][normalize-space(string())][1]")
        if not title_node:
            continue
        title = " ".join("".join(title_node[0].itertext()).split()).strip()
        if title:
            out[doc_id] = title
    return out


def _parse_collection_lang_map(root_el: etree._Element) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for node in root_el.xpath(".//*[local-name()='languageMap']/*[local-name()='lang']"):
        code = (node.get("code") or "").strip().lower()
        if not code:
            continue
        out[code] = {
            "witness": (node.get("witness") or code).strip() or code,
            "title": (node.get("title") or "").strip() or None,
            "pivot": (node.get("pivot") or "").strip().lower() in {"1", "true", "yes"},
        }
    return out


def _load_lang_titles(project_root: Path) -> dict[str, str]:
    path = _resources_dir(project_root) / "langlist.xml"
    if not path.exists():
        return {}
    try:
        tree = _load_xml(path)
    except OSError:
        return {}
    root = tree.getroot()
    out: dict[str, str] = {}
    for node in root.xpath(".//*[local-name()='language']"):
        code = (node.get("id") or "").strip().lower()
        if not code:
            continue
        title = ""
        for tag in ("title_name", "readable_name", "header_name"):
            hit = node.xpath(f"./*[local-name()='{tag}'][normalize-space(string())][1]")
            if hit:
                txt = " ".join("".join(hit[0].itertext()).split()).strip()
                if txt:
                    title = txt
                    break
        if title:
            out[code] = title
    return out


def _lang_display_title(lang_code: str, lang_titles: dict[str, str]) -> str | None:
    code = (lang_code or "").strip().lower()
    if not code:
        return None
    if code in lang_titles:
        return lang_titles[code]
    base = code.split("-", 1)[0]
    return lang_titles.get(base)


def _expand_collection_descriptor(
    descriptor_path: Path, descriptor_root: etree._Element, project_root: Path
) -> list[dict[str, Any]]:
    glob_pat = (descriptor_root.get("glob") or "").strip()
    file_re = (descriptor_root.get("filename_regex") or "").strip()
    if not glob_pat or not file_re:
        return []
    try:
        rx = re.compile(file_re)
    except re.error:
        return []

    title_lang = (descriptor_root.get("title_lang") or "eng").strip().lower()
    set_id_format = (descriptor_root.get("set_id_format") or "{setuid}").strip()
    collection_id = (descriptor_root.get("id") or descriptor_path.stem).strip() or descriptor_path.stem
    lang_map = _parse_collection_lang_map(descriptor_root)
    lang_titles = _load_lang_titles(project_root)
    doclist_titles = _load_doclist_titles(project_root)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for p in sorted(project_root.glob(glob_pat)):
        if not p.is_file() or p.suffix.lower() != ".xml":
            continue
        m = rx.match(p.name)
        if not m:
            continue
        gd = m.groupdict()
        setuid = (gd.get("setuid") or "").strip()
        lang = (gd.get("lang") or "").strip().lower()
        if not setuid or not lang:
            continue
        key = setuid
        lm = lang_map.get(lang, {})
        lang_title = _lang_display_title(lang, lang_titles)
        grouped.setdefault(key, []).append(
            {
                "path": str(p.resolve()),
                "relative_path": str(p.resolve().relative_to(project_root)),
                "id": None,
                "title": lm.get("title") or lang_title,
                "witness": (lm.get("witness") or lang).strip() or lang,
                "status": None,
                "scope": None,
                "pivot": bool(lm.get("pivot")),
                "role": "pivot" if lm.get("pivot") else None,
                "__lang": lang,
            }
        )

    rows: list[dict[str, Any]] = []
    for setuid, members in grouped.items():
        set_id = set_id_format.format(setuid=setuid, collection=collection_id)
        title = ""
        title_member = next((m for m in members if (m.get("__lang") or "") == title_lang), None)
        if title_member:
            title_path = Path(str(title_member["path"]))
            title_doc_id = _doc_id_from_filename(title_path)
            title = doclist_titles.get(title_doc_id) or _extract_doc_title(title_path)
        if not title:
            title = setuid
        rows.append(
            {
                "id": set_id,
                "title": title,
                "setuid": setuid,
                "collection_id": collection_id,
                "descriptor_path": str(descriptor_path),
                "members": [{k: v for k, v in m.items() if not str(k).startswith("__")} for m in members],
            }
        )
    return rows


def _expand_collection_descriptor_cached(
    descriptor_path: Path, descriptor_root: etree._Element, project_root: Path, force_refresh: bool = False
) -> list[dict[str, Any]]:
    cache = _load_collection_cache(project_root)
    key = str(descriptor_path.resolve())
    try:
        mtime_ns = descriptor_path.stat().st_mtime_ns
    except OSError:
        mtime_ns = -1
    rec = cache.get("descriptors", {}).get(key)
    if (
        not force_refresh
        and
        isinstance(rec, dict)
        and rec.get("mtime_ns") == mtime_ns
        and isinstance(rec.get("rows"), list)
    ):
        return list(rec.get("rows") or [])
    rows = _expand_collection_descriptor(descriptor_path, descriptor_root, project_root)
    cache.setdefault("descriptors", {})[key] = {
        "mtime_ns": mtime_ns,
        "rows": rows,
    }
    _save_collection_cache(project_root, cache)
    return rows


def load_alignment_set_manifest(
    set_id: str, project_root: Path | None = None, force_refresh: bool = False
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    path = None
    for manifest_dir in _manifest_dirs(root):
        candidate = manifest_dir / f"{set_id}.xml"
        if candidate.exists():
            path = candidate
            break
    if path is None:
        # Try collection descriptors that expand to virtual sets.
        for manifest_dir in _manifest_dirs(root):
            if not manifest_dir.exists():
                continue
            for candidate in sorted(manifest_dir.glob("*.xml")):
                try:
                    tree = _load_xml(candidate)
                    el = tree.getroot()
                except OSError:
                    continue
                if _local_tag(el) != "tuSetCollection":
                    continue
                expanded = _expand_collection_descriptor_cached(candidate, el, root, force_refresh=force_refresh)
                hit = next((row for row in expanded if str(row.get("id") or "") == set_id), None)
                if hit is None:
                    continue
                return {
                    "id": str(hit.get("id") or set_id),
                    "path": f"{candidate}#{hit.get('setuid')}",
                    "members": list(hit.get("members") or []),
                }
        raise FileNotFoundError(
            f"Alignment set manifest not found in any of: "
            + ", ".join(str(directory / f'{set_id}.xml') for directory in _manifest_dirs(root))
        )
    tree = _load_xml(path)
    manifest_root = tree.getroot()
    members: list[dict[str, Any]] = []
    for node in manifest_root.xpath(".//*[local-name()='members']/*[local-name()='doc']"):
        doc_path = node.get("path", "").strip()
        if not doc_path:
            continue
        absolute = (root / doc_path).resolve()
        members.append(
            {
                "path": str(absolute),
                "relative_path": doc_path,
                "id": node.get("id"),
                "title": node.get("title"),
                "witness": (node.get("witness") or "").strip() or None,
                "status": node.get("status"),
                "scope": node.get("scope"),
                "pivot": (node.get("pivot") or "").strip().lower() in {"1", "true", "yes"},
                "role": node.get("role"),
            }
        )
    return {
        "id": manifest_root.get("id") or set_id,
        "path": str(path),
        "members": members,
    }


def _load_discovery_patterns(project_root: Path) -> tuple[str | None, list[str]]:
    settings = _resources_dir(project_root) / "settings.xml"
    if not settings.exists():
        return None, []
    tree = _load_xml(settings)
    discovery = tree.xpath(".//*[local-name()='discovery']")
    if not discovery:
        return None, []
    node = discovery[0]
    mode = (node.get("mode") or "").strip().lower() or None
    patterns = [item.text.strip() for item in node.xpath(".//*[local-name()='pattern']") if (item.text or "").strip()]
    return mode, patterns


def _expand_pattern(pattern: str, set_id: str) -> str:
    expanded = pattern
    expanded = expanded.replace("{setuid}", set_id)
    expanded = expanded.replace("{language}", "*")
    expanded = expanded.replace("{lang}", "*")
    expanded = expanded.replace("filename", "*")
    return expanded


def auto_discover_set_documents(set_id: str, project_root: Path | None = None) -> list[str]:
    root = (project_root or Path.cwd()).resolve()
    mode, patterns = _load_discovery_patterns(root)
    if mode != "auto" or not patterns:
        return []
    discovered: list[str] = []
    for pattern in patterns:
        expanded = _expand_pattern(pattern, set_id)
        for path in root.glob(expanded):
            if path.is_file() and path.suffix.lower() == ".xml":
                resolved = str(path.resolve())
                if resolved not in discovered:
                    discovered.append(resolved)
    return discovered


def resolve_alignment_set_documents(
    set_id: str, project_root: Path | None = None, force_refresh: bool = False
) -> list[str]:
    root = (project_root or Path.cwd()).resolve()
    manifest = load_alignment_set_manifest(set_id, project_root=root, force_refresh=force_refresh)
    documents = [item["path"] for item in manifest["members"]]
    for path in auto_discover_set_documents(set_id, project_root=root):
        if path not in documents:
            documents.append(path)
    return documents


def _sort_members_by_witness(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ascending by witness id (case-folded); entries without witness follow, ordered by title then path."""

    def sort_key(row: dict[str, Any]) -> tuple[int, str, str, str]:
        w = (row.get("witness") or "").strip()
        title = (row.get("title") or "").strip()
        path = str(row.get("path") or "")
        if w:
            return (0, w.casefold(), title.casefold(), path.casefold())
        return (1, "", title.casefold(), path.casefold())

    return sorted(rows, key=sort_key)


def resolve_alignment_set_members_detailed(
    set_id: str, project_root: Path | None = None, force_refresh: bool = False
) -> list[dict[str, Any]]:
    """Ordered member rows for UI: manifest metadata plus auto-discovered paths without manifest rows."""
    root = (project_root or Path.cwd()).resolve()
    manifest = load_alignment_set_manifest(set_id, project_root=root, force_refresh=force_refresh)
    paths = resolve_alignment_set_documents(set_id, project_root=root, force_refresh=force_refresh)
    by_path = {item["path"]: item for item in manifest["members"]}
    rows: list[dict[str, Any]] = []
    for path in paths:
        base = by_path.get(path)
        if base is not None:
            rows.append(dict(base))
            continue
        rows.append(
            {
                "path": path,
                "relative_path": None,
                "id": None,
                "title": None,
                "witness": None,
                "status": None,
                "scope": None,
                "pivot": False,
                "role": None,
            }
        )
    return _sort_members_by_witness(rows)


def manifests_write_directory(project_root: Path) -> Path:
    """Preferred directory for new alignment-set manifest files."""
    return project_root / "Alignments" / "Sets"


def relative_path_under_project(project_root: Path, doc_path: Path | str) -> str:
    """Return POSIX path of ``doc_path`` relative to project root; raise if outside root."""
    root = project_root.resolve()
    p = Path(doc_path).expanduser()
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()
    try:
        rel = p.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Document path {doc_path} is not under project root {root}") from exc
    return str(rel).replace("\\", "/")


def manifest_file_path(set_id: str, project_root: Path) -> Path | None:
    """Return path to an existing on-disk manifest ``{set_id}.xml``, or ``None``."""
    root = project_root.resolve()
    for manifest_dir in _manifest_dirs(root):
        candidate = manifest_dir / f"{set_id}.xml"
        if candidate.is_file():
            return candidate
    return None


def _manifest_root_must_be_tuset(tree: etree._ElementTree) -> etree._Element:
    el = tree.getroot()
    if _local_tag(el) != "tuSet":
        raise ValueError("Manifest root must be tuSet (not a collection descriptor)")
    return el


def create_alignment_set_manifest(
    project_root: Path,
    set_id: str,
    *,
    title: str = "",
) -> Path:
    """Create ``Alignments/Sets/{set_id}.xml`` with an empty ``members`` element.

    Raises ``FileExistsError`` if the manifest file already exists.
    """
    root = project_root.resolve()
    out_dir = manifests_write_directory(root)
    path = out_dir / f"{set_id}.xml"
    if path.exists():
        raise FileExistsError(f"Alignment set manifest already exists: {path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    tu_set = etree.Element("tuSet")
    tu_set.set("id", set_id)
    if title.strip():
        tu_set.set("title", title.strip())
    etree.SubElement(tu_set, "members")
    tree = etree.ElementTree(tu_set)
    tree.write(str(path), pretty_print=True, xml_declaration=True, encoding="utf-8")
    return path


def _member_dict_to_doc_attrs(member: dict[str, Any]) -> dict[str, str]:
    attrs: dict[str, str] = {}
    path = (member.get("relative_path") or member.get("path") or "").strip()
    if path:
        attrs["path"] = path
    for key in ("id", "title", "witness", "status", "scope", "role"):
        val = member.get(key)
        if val is not None and str(val).strip():
            attrs[key] = str(val).strip()
    if member.get("pivot") or (str(member.get("role") or "").strip().lower() == "pivot"):
        attrs["pivot"] = "true"
    return attrs


def _save_tuset_manifest(path: Path, tu_set_el: etree._Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree = etree.ElementTree(tu_set_el)
    tree.write(str(path), pretty_print=True, xml_declaration=True, encoding="utf-8")


def write_alignment_set_manifest_from_manifest_dict(manifest: dict[str, Any], project_root: Path | None = None) -> Path:
    """Write or overwrite a ``tuSet`` manifest from a manifest dict (same shape as ``load_alignment_set_manifest`` output).

    Only file-backed manifests are supported. Path is taken from ``manifest["path"]`` when it points to a real file;
    otherwise writes to ``manifests_write_directory / {id}.xml``.
    """
    root = (project_root or Path.cwd()).resolve()
    set_id = str(manifest.get("id") or "").strip()
    if not set_id:
        raise ValueError("manifest id is required")
    raw_path = manifest.get("path")
    path: Path | None = None
    if isinstance(raw_path, str) and raw_path and "#" not in raw_path:
        candidate = Path(raw_path)
        if candidate.is_file():
            path = candidate
    if path is None:
        path = manifests_write_directory(root) / f"{set_id}.xml"
    tu_set = etree.Element("tuSet")
    tu_set.set("id", set_id)
    title = (manifest.get("title") or "").strip()
    if title:
        tu_set.set("title", title)
    members_el = etree.SubElement(tu_set, "members")
    for row in manifest.get("members") or []:
        rel = (row.get("relative_path") or "").strip()
        if not rel:
            abs_path = str(row.get("path") or "").strip()
            if abs_path:
                rel = relative_path_under_project(root, abs_path)
        if not rel:
            continue
        doc_el = etree.SubElement(members_el, "doc")
        doc_el.set("path", rel)
        m = dict(row)
        m["relative_path"] = rel
        m.pop("path", None)
        for attr_name, attr_val in _member_dict_to_doc_attrs(m).items():
            if attr_name == "path":
                continue
            doc_el.set(attr_name, attr_val)
    _save_tuset_manifest(path, tu_set)
    return path


def add_alignment_set_member(
    set_id: str,
    doc_path: Path | str,
    project_root: Path | None = None,
    *,
    member_id: str | None = None,
    title: str | None = None,
    witness: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    role: str | None = None,
    pivot: bool | None = None,
) -> Path:
    """Append a ``doc`` to the on-disk manifest for ``set_id``.

    Raises ``FileNotFoundError`` if no manifest file exists yet (call ``create_alignment_set_manifest`` first).
    """
    root = (project_root or Path.cwd()).resolve()
    rel = relative_path_under_project(root, doc_path)
    path = manifest_file_path(set_id, root)
    if path is None:
        raise FileNotFoundError(
            f"No manifest file for set `{set_id}`; create one with create_alignment_set_manifest first."
        )
    tree = _load_xml(path)
    tu_set = _manifest_root_must_be_tuset(tree)
    members_el = tu_set.xpath(".//*[local-name()='members']")
    if not members_el:
        members_el_node = etree.SubElement(tu_set, "members")
    else:
        members_el_node = members_el[0]
    for node in members_el_node.xpath("./*[local-name()='doc']"):
        if (node.get("path") or "").strip() == rel:
            raise ValueError(f"Document already in set: {rel}")
    doc_el = etree.SubElement(members_el_node, "doc")
    doc_el.set("path", rel)
    if member_id is not None and str(member_id).strip():
        doc_el.set("id", str(member_id).strip())
    if title is not None and str(title).strip():
        doc_el.set("title", str(title).strip())
    if witness is not None and str(witness).strip():
        doc_el.set("witness", str(witness).strip())
    if status is not None and str(status).strip():
        doc_el.set("status", str(status).strip())
    if scope is not None and str(scope).strip():
        doc_el.set("scope", str(scope).strip())
    if role is not None and str(role).strip():
        doc_el.set("role", str(role).strip())
    if pivot is True:
        doc_el.set("pivot", "true")
    _save_tuset_manifest(path, tu_set)
    return path


_DOC_META_UNSET = object()


def update_alignment_set_member(
    set_id: str,
    doc_path: Path | str,
    project_root: Path | None = None,
    *,
    witness: object | str | None = _DOC_META_UNSET,
    title: object | str | None = _DOC_META_UNSET,
) -> Path:
    """Update ``witness`` / ``title`` on an existing manifest ``doc`` row.

    Pass :data:`_DOC_META_UNSET` for a field to leave it unchanged.
    Pass ``""`` or ``None`` to remove that attribute from the element.
    """
    root = (project_root or Path.cwd()).resolve()
    rel = relative_path_under_project(root, doc_path)
    path = manifest_file_path(set_id, root)
    if path is None:
        raise FileNotFoundError(f"No manifest file for set `{set_id}`")
    tree = _load_xml(path)
    tu_set = _manifest_root_must_be_tuset(tree)
    members_el = tu_set.xpath(".//*[local-name()='members']")
    if not members_el:
        raise ValueError("Manifest has no members element")
    found = False
    for node in members_el[0].xpath("./*[local-name()='doc']"):
        if (node.get("path") or "").strip() != rel:
            continue
        found = True
        if witness is not _DOC_META_UNSET:
            w = (str(witness).strip() if witness is not None else "") or ""
            if w:
                node.set("witness", w)
            elif "witness" in node.attrib:
                del node.attrib["witness"]
        if title is not _DOC_META_UNSET:
            t = (str(title).strip() if title is not None else "") or ""
            if t:
                node.set("title", t)
            elif "title" in node.attrib:
                del node.attrib["title"]
        break
    if not found:
        raise ValueError(f"No member with path {rel} in set `{set_id}`")
    _save_tuset_manifest(path, tu_set)
    return path


def remove_alignment_set_member(set_id: str, doc_path: Path | str, project_root: Path | None = None) -> Path:
    """Remove a ``doc`` whose path matches ``doc_path`` (absolute or project-relative)."""
    root = (project_root or Path.cwd()).resolve()
    rel = relative_path_under_project(root, doc_path)
    path = manifest_file_path(set_id, root)
    if path is None:
        raise FileNotFoundError(f"No manifest file for set `{set_id}`")
    tree = _load_xml(path)
    tu_set = _manifest_root_must_be_tuset(tree)
    members_el = tu_set.xpath(".//*[local-name()='members']")
    if not members_el:
        raise ValueError("Manifest has no members element")
    removed = False
    for node in list(members_el[0].xpath("./*[local-name()='doc']")):
        if (node.get("path") or "").strip() == rel:
            members_el[0].remove(node)
            removed = True
            break
    if not removed:
        raise ValueError(f"No member with path {rel} in set `{set_id}`")
    _save_tuset_manifest(path, tu_set)
    return path


def set_alignment_set_pivot(
    set_id: str,
    doc_path: Path | str,
    project_root: Path | None = None,
    *,
    clear_others: bool = True,
) -> Path:
    """Mark ``doc_path`` as pivot (``pivot="true"``). Optionally clear pivot on other members."""
    root = (project_root or Path.cwd()).resolve()
    rel = relative_path_under_project(root, doc_path)
    path = manifest_file_path(set_id, root)
    if path is None:
        raise FileNotFoundError(f"No manifest file for set `{set_id}`")
    tree = _load_xml(path)
    tu_set = _manifest_root_must_be_tuset(tree)
    members_el = tu_set.xpath(".//*[local-name()='members']")
    if not members_el:
        raise ValueError("Manifest has no members element")
    found = False
    for node in members_el[0].xpath("./*[local-name()='doc']"):
        p = (node.get("path") or "").strip()
        if p == rel:
            node.set("pivot", "true")
            found = True
        elif clear_others and node.get("pivot"):
            del node.attrib["pivot"]
    if not found:
        raise ValueError(f"No member with path {rel} in set `{set_id}`")
    _save_tuset_manifest(path, tu_set)
    return path


def list_pair_json_candidates_for_set(
    set_id: str,
    project_root: Path | None = None,
    *,
    max_files: int = 200,
) -> list[dict[str, Any]]:
    """
    List project-relative pair JSON paths under ``Alignments/Pairs/{set_id}/`` (newest first).

    Each item has at least ``path`` and ``mtime``; ``version1`` / ``version2`` are filled when the
    file is valid JSON (used by UIs to pick the pair file for pivot/target witnesses).
    """
    root = (project_root or Path.cwd()).resolve()
    seg = Path(str(set_id).replace("\\", "/")).name
    if not seg or seg in {".", ".."} or ".." in str(set_id):
        return []
    pairs_dir = root / "Alignments" / "Pairs" / seg
    if not pairs_dir.is_dir():
        return []
    collected: list[dict[str, Any]] = []
    for pth in pairs_dir.rglob("*.json"):
        if not pth.is_file():
            continue
        try:
            rel = pth.relative_to(root).as_posix()
        except ValueError:
            continue
        snap: dict[str, Any] = {"path": rel, "mtime": int(pth.stat().st_mtime)}
        try:
            chunk = pth.read_text(encoding="utf-8", errors="replace")[:262144]
            data = json.loads(chunk)
        except (OSError, json.JSONDecodeError):
            collected.append(snap)
            continue
        if isinstance(data, dict):
            v1 = str(data.get("version1") or "").replace("\\", "/").strip() or None
            v2 = str(data.get("version2") or "").replace("\\", "/").strip() or None
            wf = data.get("flexalign_workflow")
            if isinstance(wf, dict):
                if not v1 and wf.get("source_xml"):
                    v1 = str(wf["source_xml"]).replace("\\", "/").strip() or None
                if not v2 and wf.get("target_xml"):
                    v2 = str(wf["target_xml"]).replace("\\", "/").strip() or None
            if v1:
                snap["version1"] = v1
            if v2:
                snap["version2"] = v2
        collected.append(snap)
    collected.sort(key=lambda r: int(r.get("mtime") or 0), reverse=True)
    return collected[: max(1, min(2000, max_files))]


def resolve_alignment_set_plan(
    set_id: str, project_root: Path | None = None, pivot_mode: str = "first", force_refresh: bool = False
) -> dict[str, Any]:
    root = (project_root or Path.cwd()).resolve()
    manifest = load_alignment_set_manifest(set_id, project_root=root, force_refresh=force_refresh)
    documents = resolve_alignment_set_documents(set_id, project_root=root, force_refresh=force_refresh)
    if len(documents) < 2:
        raise ValueError(f"Set `{set_id}` needs at least two documents, found {len(documents)}")

    pivot_candidates = []
    for member in manifest["members"]:
        if member.get("pivot") or (member.get("role") or "").strip().lower() == "pivot":
            pivot_candidates.append(member["path"])

    pivots = [candidate for candidate in pivot_candidates if candidate in documents]
    if not pivots:
        pivots = [documents[0]]

    if pivot_mode not in {"first", "all"}:
        raise ValueError(f"Unsupported pivot_mode: {pivot_mode}")

    if pivot_mode == "all":
        active_pivots = pivots
    else:
        active_pivots = [pivots[0]]

    pairs: list[tuple[str, str]] = []
    for pivot in active_pivots:
        for target in documents:
            if target == pivot:
                continue
            pairs.append((pivot, target))
    pivot = active_pivots[0]
    targets = [path for path in documents if path != pivot]
    return {
        "set": set_id,
        "pivot": pivot,
        "pivots": active_pivots,
        "targets": targets,
        "pairs": pairs,
        "documents": documents,
    }

