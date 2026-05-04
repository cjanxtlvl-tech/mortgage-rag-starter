#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "raw" / "veecasa_rag_qa_expansion_v1.json"
OUTPUT_PATH = ROOT / "data" / "raw" / "veecasa_rag_qa_expansion_v1_humanized.json"

QUESTION_PREFIXES = [
    "How do I",
    "How much",
    "Can I",
    "Do I need",
    "What happens if",
    "How does",
    "Why does",
    "Is it possible to",
    "What should I",
    "Which",
]


def clean_space(text: str) -> str:
    return " ".join(text.split()).strip()


def title_context(rec: dict[str, Any]) -> str:
    return clean_space(str(rec.get("title", "")))


def conversationalize(question: str, rec: dict[str, Any], idx: int) -> str:
    q = clean_space(question)
    if not q:
        return q

    q = q.rstrip(".!")
    lower = q.lower()
    title = title_context(rec)

    m = re.match(r"^What should I understand first about\s+(.+?)\??$", q, flags=re.I)
    if m:
        topic = clean_space(m.group(1))
        style = idx % 3
        if style == 0:
            q = f"What do I need to know first about {topic}"
        elif style == 1:
            q = f"How does {topic} work for someone like me"
        else:
            q = f"Can you explain the basics of {topic}"
    elif re.match(r"^How do I know if I qualify for\s+(.+?)\??$", q, flags=re.I):
        topic = clean_space(re.sub(r"^How do I know if I qualify for\s+", "", q, flags=re.I)).rstrip("?")
        q = f"Do I qualify for {topic}"
    elif re.match(r"^Which documents should I prepare for\s+(.+?)\??$", q, flags=re.I):
        topic = clean_space(re.sub(r"^Which documents should I prepare for\s+", "", q, flags=re.I)).rstrip("?")
        q = f"What documents do I need for {topic}"
    elif re.match(r"^What costs and monthly payment factors should I review for\s+(.+?)\??$", q, flags=re.I):
        topic = clean_space(re.sub(r"^What costs and monthly payment factors should I review for\s+", "", q, flags=re.I)).rstrip("?")
        q = f"How much could monthly payments and costs be for {topic}"
    elif re.match(r"^What common mistakes should I avoid when using\s+(.+?)\??$", q, flags=re.I):
        topic = clean_space(re.sub(r"^What common mistakes should I avoid when using\s+", "", q, flags=re.I)).rstrip("?")
        q = f"What mistakes should I avoid with {topic}"
    elif re.match(r"^What is the best next step to move forward with\s+(.+?)\??$", q, flags=re.I):
        topic = clean_space(re.sub(r"^What is the best next step to move forward with\s+", "", q, flags=re.I)).rstrip("?")
        q = f"What should I do next to move forward with {topic}"
    else:
        q = q[0].upper() + q[1:] if q else q

    q = clean_space(q)

    if title and title.lower() in lower and "first-time" in lower and "as a first-time buyer" not in q.lower():
        q = q.rstrip("?") + " as a first-time buyer"

    if not q.endswith("?"):
        q = q + "?"

    return q


def normalize_for_dupes(question: str) -> str:
    s = question.lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def ensure_varied_starts(questions: list[str]) -> None:
    starts = set()
    for q in questions:
        first_two = " ".join(q.split()[:2]).lower()
        starts.add(first_two)
    if len(starts) < 4:
        raise ValueError("Low phrasing diversity detected after rewrite; fewer than 4 opening patterns found.")


def main() -> None:
    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of QA objects")

    changed = 0
    examples: list[tuple[str, str]] = []
    rewritten_questions: list[str] = []

    output: list[dict[str, Any]] = []
    for idx, rec in enumerate(data):
        if not isinstance(rec, dict):
            raise ValueError(f"Record at index {idx} is not an object")

        original_q = clean_space(str(rec.get("question", "")))
        new_q = conversationalize(original_q, rec, idx)

        if not new_q:
            raise ValueError(f"Empty question after rewrite at index {idx}, id={rec.get('id')}")

        new_rec = dict(rec)
        new_rec["question"] = new_q
        output.append(new_rec)
        rewritten_questions.append(new_q)

        if new_q != original_q:
            changed += 1
            if len(examples) < 10:
                examples.append((original_q, new_q))

    seen: dict[str, str] = {}
    dupes: list[tuple[str, str]] = []
    for q in rewritten_questions:
        key = normalize_for_dupes(q)
        if key in seen:
            dupes.append((seen[key], q))
        else:
            seen[key] = q

    if dupes:
        sample = "\n".join([f"- {a} == {b}" for a, b in dupes[:5]])
        raise ValueError(f"Duplicate questions detected after rewrite:\n{sample}")

    ensure_varied_starts(rewritten_questions)

    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Total questions processed: {len(output)}")
    print(f"Number of questions changed: {changed}")
    print("10 before/after examples:")
    for i, (before, after) in enumerate(examples[:10], start=1):
        print(f"{i:>2}. BEFORE: {before}")
        print(f"    AFTER:  {after}")


if __name__ == "__main__":
    main()