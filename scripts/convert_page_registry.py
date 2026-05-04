#!/usr/bin/env python3
"""Convert page registry XLSX to JSON while preserving columns.

Input:
  data/link_routing/page_registry.xlsx
Output:
  data/link_routing/page_registry.json
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile


NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_to_idx(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return max(0, value - 1)


def _parse_xlsx_rows(path: Path) -> list[list[str]]:
    with ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in shared_root.findall("a:si", NS):
                text = "".join(t.text or "" for t in si.findall(".//a:t", NS))
                shared.append(text)

        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        rows = []
        for row in sheet.findall(".//a:sheetData/a:row", NS):
            cells = {}
            max_idx = -1
            for c in row.findall("a:c", NS):
                ref = c.attrib.get("r", "")
                idx = _col_to_idx(ref)
                max_idx = max(max_idx, idx)
                t = c.attrib.get("t")
                v_node = c.find("a:v", NS)
                value = ""
                if v_node is not None and v_node.text is not None:
                    raw = v_node.text
                    if t == "s" and raw.isdigit():
                        shared_idx = int(raw)
                        if 0 <= shared_idx < len(shared):
                            value = shared[shared_idx]
                    else:
                        value = raw
                cells[idx] = value.strip()
            if max_idx >= 0:
                row_values = [cells.get(i, "") for i in range(max_idx + 1)]
                rows.append(row_values)
        return rows


def _split_keywords(value: str):
    value = value.strip()
    if not value:
        return []
    if "," not in value:
        return value
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    xlsx_path = root / "data" / "link_routing" / "page_registry.xlsx"
    json_path = root / "data" / "link_routing" / "page_registry.json"

    if not xlsx_path.exists():
        raise FileNotFoundError(f"Missing file: {xlsx_path}")

    rows = _parse_xlsx_rows(xlsx_path)
    if not rows:
        raise ValueError("No rows found in XLSX")

    headers = [h.strip() for h in rows[0]]
    if not any(headers):
        raise ValueError("Header row is empty")

    records: list[dict[str, object]] = []
    invalid_url_count = 0

    for row in rows[1:]:
        padded = row + [""] * (len(headers) - len(row))
        rec: dict[str, object] = {}
        for i, key in enumerate(headers):
            if not key:
                continue
            val = padded[i].strip() if i < len(padded) else ""
            if key.lower() == "keywords":
                rec[key] = _split_keywords(val)
            else:
                rec[key] = val

        url_key = next((k for k in rec.keys() if k.lower() == "url"), None)
        if url_key:
            url_val = str(rec.get(url_key, "")).strip()
            if url_val and not url_val.startswith("https://veecasa.com/"):
                invalid_url_count += 1
                print(f"WARNING: Invalid URL prefix skipped: {url_val}")
                continue

        if any(str(v).strip() for v in rec.values()):
            records.append(rec)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Converted rows: {len(records)}")
    print(f"Invalid URL rows skipped: {invalid_url_count}")
    print(f"Output: {json_path}")


if __name__ == "__main__":
    main()
