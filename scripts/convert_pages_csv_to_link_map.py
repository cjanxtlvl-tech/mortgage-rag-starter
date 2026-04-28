#!/usr/bin/env python3
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

CSV_PATH = Path("data/site_pages/all_pages.csv")
OUT_PATH = Path("data/site_pages/veecasa_link_map.json")

def slug_to_keywords(url):
    path = urlparse(url).path.strip("/")
    words = re.sub(r"[-_]+", " ", path).lower()
    words = re.sub(r"\bnj\b", "new jersey", words)
    return sorted(set([words] + words.split()))

def infer_intent(url):
    u = url.lower()
    if any(x in u for x in ["form", "preapproval", "apply", "qualify"]):
        return "conversion"
    if any(x in u for x in ["calculator", "deal-analyzer"]):
        return "tool"
    return "education"

def read_urls():
    urls = []
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = [h.lower().strip() for h in reader.fieldnames or []]

        for row in reader:
            value = None
            for key in row:
                if key and key.lower().strip() in {"url", "link", "permalink", "page url"}:
                    value = row[key]
                    break

            if not value:
                for cell in row.values():
                    if isinstance(cell, str) and cell.startswith("https://veecasa.com"):
                        value = cell
                        break

            if value:
                url = value.strip()
                if url.startswith("https://veecasa.com"):
                    urls.append(url)

    return sorted(set(urls))

def main():
    urls = read_urls()

    link_map = []
    for url in urls:
        link_map.append({
            "url": url,
            "slug_keywords": slug_to_keywords(url),
            "manual_keywords": [],
            "intent": infer_intent(url),
            "priority": 1
        })

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(link_map, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Created {OUT_PATH}")
    print(f"Pages converted: {len(link_map)}")

if __name__ == "__main__":
    main()
