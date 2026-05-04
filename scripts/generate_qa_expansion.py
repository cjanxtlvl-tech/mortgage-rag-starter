#!/usr/bin/env python3
"""Generate QA expansion records using approved page registry links only."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


TARGET_NEW_RECORDS = 366
LAST_UPDATED = "2026-05-04"
APPROVED_PREFIX = "https://veecasa.com/"

INTENT_PLAN = [
    ("overview", "education"),
    ("qualification", "qualification"),
    ("documents", "qualification"),
    ("cost/payment", "education"),
    ("common mistakes", "education"),
    ("next step/conversion", "conversion"),
]

ACTION_TRIGGERS = {
    "conversion",
    "qualification",
    "purchase",
    "refinance",
    "fha",
    "dscr",
    "investment",
    "commercial",
    "sba",
    "hard_money",
    "document-prep",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_question(text: str) -> str:
    return clean_text(text).lower()


def slug_to_title(url: str) -> str:
    path = url.replace(APPROVED_PREFIX, "").strip("/")
    if not path:
        return "VeeCasa Mortgage Guide"
    words = [w for w in re.split(r"[-_/]+", path) if w]
    return " ".join(word.upper() if word in {"fha", "va", "apr", "dscr", "sba"} else word.capitalize() for word in words)


def slug_keywords(url: str) -> list[str]:
    path = url.replace(APPROVED_PREFIX, "").strip("/")
    if not path:
        return ["mortgage", "veecasa"]
    words = [w.lower() for w in re.split(r"[-_/]+", path) if w]
    words.extend(["mortgage", "home", "loan"])
    # preserve order, remove duplicates
    seen = set()
    out = []
    for w in words:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out[:12]


def infer_category_intent(url: str) -> tuple[str, str]:
    s = url.lower()
    if any(k in s for k in ["dscr", "investment", "commercial", "sba", "hard-money"]):
        return "loan_product", "investment"
    if any(k in s for k in ["fha", "va", "usda", "conventional", "refinance", "cash-out"]):
        return "loan_product", "qualification"
    if any(k in s for k in ["calculator", "payment", "apr", "rate", "closing-cost"]):
        return "education", "comparison"
    return "education", "education"


def should_offer_action(intent: str, category: str, tags: list[str], question: str) -> bool:
    text = f"{intent} {category} {' '.join(tags)} {question.lower()}"
    return any(trigger in text for trigger in ACTION_TRIGGERS)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def extract_registry_pages(registry_data: Any) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    if not isinstance(registry_data, list):
        return pages

    for row in registry_data:
        if not isinstance(row, dict):
            continue
        url_key = next((k for k in row.keys() if k.lower() == "url"), None)
        if not url_key:
            continue
        url = clean_text(row.get(url_key, ""))
        if not url.startswith(APPROVED_PREFIX):
            continue

        title = clean_text(row.get("title", "")) or slug_to_title(url)
        topic = clean_text(row.get("topic", "")) or title
        raw_keywords = row.get("keywords", [])
        if isinstance(raw_keywords, list):
            kws = [clean_text(k).lower() for k in raw_keywords if clean_text(k)]
        elif isinstance(raw_keywords, str):
            kws = [clean_text(k).lower() for k in raw_keywords.split(",") if clean_text(k)]
        else:
            kws = []
        if not kws:
            kws = slug_keywords(url)

        category = clean_text(row.get("category", ""))
        intent = clean_text(row.get("intent", ""))
        if not category or not intent:
            inferred_category, inferred_intent = infer_category_intent(url)
            category = category or inferred_category
            intent = intent or inferred_intent

        source_id = clean_text(row.get("source_id", "")) or f"registry-{len(pages)+1:04d}"
        pages.append(
            {
                "source_id": source_id,
                "url": url,
                "title": title,
                "topic": topic,
                "keywords": kws,
                "category": category,
                "intent": intent,
                "source_url": clean_text(row.get("source_url", "")) or url,
            }
        )
    return pages


def build_question(topic: str, title: str, intent_name: str, idx: int) -> str:
    if intent_name == "overview":
        return f"What should I understand first about {topic}?"
    if intent_name == "qualification":
        return f"How do I know if I qualify for {title}?"
    if intent_name == "documents":
        return f"Which documents should I prepare for {title}?"
    if intent_name == "cost/payment":
        return f"What costs and monthly payment factors should I review for {topic}?"
    if intent_name == "common mistakes":
        return f"What common mistakes should I avoid when using {title}?"
    return f"What is the best next step to move forward with {topic}?"


def build_answer(topic: str, title: str, intent_name: str, url: str) -> str:
    base_map = {
        "overview": f"{title} can help you understand how this mortgage path works, who it may fit, and the tradeoffs to evaluate before applying.",
        "qualification": "Qualification usually depends on credit profile, income or cash flow documentation, debt obligations, property details, and lender-specific overlays.",
        "documents": "Preparing a clear document package early can reduce delays and improve lender response times during review and underwriting.",
        "cost/payment": "Reviewing payment structure, fees, reserves, and long-term affordability helps you compare options and avoid surprises at closing.",
        "common mistakes": "A common mistake is choosing too quickly without comparing guidelines, total costs, and timeline fit across multiple lender options.",
        "next step/conversion": "A practical next step is to organize your goals and documents, then request scenario-based guidance to choose the strongest path.",
    }
    body = base_map[intent_name]
    return f"{body} You can learn more here: {url}"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    qa_path = root / "data" / "raw" / "veecasa_rag_qa_optimized.json"
    registry_path = root / "data" / "link_routing" / "page_registry.json"
    out_path = root / "data" / "raw" / "veecasa_rag_qa_expansion_v1.json"

    qa_data = load_json(qa_path)
    registry_data = load_json(registry_path)

    if not isinstance(qa_data, list):
        raise ValueError("Expected veecasa_rag_qa_optimized.json to be a list")

    pages = extract_registry_pages(registry_data)
    if not pages:
        raise ValueError("No valid approved pages found in page_registry.json")

    existing_norm_questions = {
        normalize_question(item.get("question", ""))
        for item in qa_data
        if isinstance(item, dict) and clean_text(item.get("question", ""))
    }

    generated: list[dict[str, Any]] = []
    skipped_no_confident_match = 0
    page_counters: dict[str, int] = defaultdict(int)

    safety_keywords = {
        "rate guarantee",
        "guaranteed approval",
        "legal advice",
        "underwriting guarantee",
    }

    while len(generated) < TARGET_NEW_RECORDS:
        grew = False
        for page in pages:
            if len(generated) >= TARGET_NEW_RECORDS:
                break
            for intent_name, intent_value in INTENT_PLAN:
                if len(generated) >= TARGET_NEW_RECORDS:
                    break

                candidate_q = build_question(page["topic"], page["title"], intent_name, page_counters[page["url"]])
                norm_q = normalize_question(candidate_q)
                if not norm_q or norm_q in existing_norm_questions:
                    skipped_no_confident_match += 1
                    continue

                ans = build_answer(page["topic"], page["title"], intent_name, page["url"])
                lower_ans = ans.lower()
                if any(bad in lower_ans for bad in safety_keywords):
                    skipped_no_confident_match += 1
                    continue

                page_counters[page["url"]] += 1
                idx = page_counters[page["url"]]
                rec_id = f"qa-exp-{re.sub(r'[^a-z0-9]+', '-', page['title'].lower()).strip('-')}-{idx}"

                tags = page["keywords"][:8]
                if "page" not in tags:
                    tags.append("page")

                record = {
                    "id": rec_id,
                    "source_id": page["source_id"],
                    "question": candidate_q,
                    "answer": ans,
                    "recommended_link": page["url"],
                    "source_url": page["source_url"],
                    "title": page["title"],
                    "category": page["category"],
                    "location": "",
                    "intent": intent_value if intent_name != "next step/conversion" else "conversion",
                    "tags": tags,
                    "last_updated": LAST_UPDATED,
                }

                if should_offer_action(record["intent"], record["category"], tags, candidate_q):
                    record["suggested_next_action"] = "offer_start_rasa_application"

                generated.append(record)
                existing_norm_questions.add(norm_q)
                grew = True

                if len(generated) >= TARGET_NEW_RECORDS:
                    break

        if not grew:
            # unable to create more non-duplicate strong records from current templates/pages
            break

    out_path.write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Existing QA count: {len(qa_data)}")
    print(f"Registry page count: {len(pages)}")
    print(f"New QA count generated: {len(generated)}")
    print(f"Skipped records due to no confident registry match: {skipped_no_confident_match}")
    print(f"Final projected total: {len(qa_data) + len(generated)}")
    print(f"Output: {out_path}")
    print("\nTop 10 sample generated records:")
    for i, rec in enumerate(generated[:10], start=1):
        print(f"{i:>2}. {rec['question']} -> {rec['recommended_link']}")


if __name__ == "__main__":
    main()
