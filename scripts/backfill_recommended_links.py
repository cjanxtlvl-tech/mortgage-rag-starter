#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

RAW_DIR = Path("data/raw")
FALLBACK_URL = "https://veecasa.com/buyer-education-hub"

TOPIC_MAP = [
    (("closing cost", "cash to close", "escrow", "prepaid", "title insurance"), "https://veecasa.com/closing-cost-demystified/"),
    (("seller concession", "seller credit", "seller pay closing costs"), "https://veecasa.com/sellers-concessions"),
    (("grant", "down payment assistance", "first-time buyer program"), "https://veecasa.com/state-and-local-housing-grants"),
    (("dti", "debt to income", "debt-to-income"), "https://veecasa.com/debt-to-income-ratio"),
    (("calculator", "monthly payment", "payment estimate"), "https://veecasa.com/mortgage-calculator-explained"),
    (("credit", "fico", "credit score", "credit repair"), "https://veecasa.com/credit-score"),
    (("refinance", "cash-out", "rate and term"), "https://veecasa.com/when-to-refinance"),
    (("dscr", "rental property", "investor", "investment property", "airbnb", "vrbo"), "https://veecasa.com/dscr-loans"),
    (("deal analysis", "cap rate", "cash-on-cash", "rental return"), "https://veecasa.com/deal-analyzer"),
    (("mortgage types", "fha vs conventional", "conventional", "arm", "fixed-rate"), "https://veecasa.com/types-of-mortgage"),
    (("saving", "save for home", "budget", "planning to buy"), "https://veecasa.com/saving-for-your-home"),
    (("home buying", "first home", "buying process", "realtor", "inspection", "appraisal"), "https://veecasa.com/home-buying"),
    (("preapproval", "qualify", "apply", "application", "loan officer", "ready to start"), "https://veecasa.com/form"),
]

HIGH_INTENT_TERMS = (
    "preapproval", "pre-approval", "qualify", "apply", "application",
    "loan officer", "ready to start", "get started", "start the process",
    "buy a home", "purchase a home", "refinance", "dscr loan"
)

def valid_veecasa_url(value):
    return isinstance(value, str) and value.strip().startswith("https://veecasa.com/")

def detect_link(record):
    text = " ".join([
        str(record.get("title", "")),
        str(record.get("question", "")),
        str(record.get("answer", "")),
        str(record.get("category", "")),
    ]).lower()

    for terms, url in TOPIC_MAP:
        if any(term in text for term in terms):
            return url, False

    return FALLBACK_URL, True

def is_high_intent(record):
    text = " ".join([
        str(record.get("title", "")),
        str(record.get("question", "")),
        str(record.get("answer", "")),
        str(record.get("category", "")),
    ]).lower()

    return any(term in text for term in HIGH_INTENT_TERMS)

def iter_records(obj):
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                yield item
    elif isinstance(obj, dict):
        if isinstance(obj.get("records"), list):
            for item in obj["records"]:
                if isinstance(item, dict):
                    yield item
        else:
            yield obj

def main():
    files_scanned = 0
    records_updated = 0
    links_added = 0
    actions_added = 0
    defaulted = 0

    for path in sorted(RAW_DIR.rglob("*.json")):
        files_scanned += 1

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        changed = False

        for record in iter_records(data):
            record_changed = False

            if not valid_veecasa_url(record.get("recommended_link")):
                link, was_default = detect_link(record)
                record["recommended_link"] = link
                links_added += 1
                record_changed = True
                if was_default:
                    defaulted += 1

            if is_high_intent(record) and not record.get("suggested_next_action"):
                record["suggested_next_action"] = "offer_start_rasa_application"
                actions_added += 1
                record_changed = True

            if record_changed:
                records_updated += 1
                changed = True

        if changed:
            backup = path.with_suffix(path.suffix + ".bak")
            if not backup.exists():
                shutil.copy2(path, backup)

            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

    print("Backfill complete")
    print(f"Files scanned: {files_scanned}")
    print(f"Records updated: {records_updated}")
    print(f"Links added/fixed: {links_added}")
    print(f"Actions added: {actions_added}")
    print(f"Fallback/defaulted records: {defaulted}")

if __name__ == "__main__":
    main()
