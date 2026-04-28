import json
from pathlib import Path

FILE_PATH = Path("data/site_pages/veecasa_link_map.json")

PATCHES = {
    "/closing-cost-demystified/": {
        "keywords": [
            "closing costs","cash to close","buyer closing costs","seller closing costs",
            "escrow fees","title insurance","prepaid taxes","prepaid insurance",
            "settlement fees","closing disclosure"
        ],
        "priority": 5
    },
    "/sellers-concessions/": {
        "keywords": [
            "seller concessions","seller credit","seller pays closing costs",
            "closing cost assistance","negotiating closing costs",
            "concessions fha","concessions conventional"
        ],
        "priority": 5
    },
    "/credit-score/": {
        "keywords": [
            "credit score","fico score","minimum credit score mortgage",
            "credit needed for fha","credit needed for conventional",
            "improve credit","fix credit","credit repair","low credit mortgage"
        ],
        "priority": 5
    },
    "/debt-to-income-ratio/": {
        "keywords": [
            "dti","debt to income ratio","max dti mortgage",
            "calculate dti","front end ratio","back end ratio",
            "qualify with high dti"
        ],
        "priority": 5
    },
    "/mortgage-calculator-explained/": {
        "keywords": [
            "mortgage calculator","monthly payment",
            "estimate mortgage payment","loan payment estimate",
            "piti","principal interest taxes insurance"
        ],
        "priority": 4
    },
    "/home-buying/": {
        "keywords": [
            "how to buy a house","home buying process",
            "steps to buy a home","first time homebuyer process",
            "offer process","closing process"
        ],
        "priority": 5
    },
    "/state-and-local-housing-grants/": {
        "keywords": [
            "down payment assistance","first time homebuyer grants",
            "housing grants","0% down programs",
            "state housing programs","local homebuyer programs"
        ],
        "priority": 5
    },
    "/when-to-refinance/": {
        "keywords": [
            "refinance","cash out refinance","rate and term refinance",
            "should i refinance","refinance savings"
        ],
        "priority": 5
    },
    "/dscr-loans/": {
        "keywords": [
            "dscr loan","investment property loan","rental income mortgage",
            "airbnb loan","investor financing","cash flow property loan"
        ],
        "priority": 5
    },
    "/deal-analyzer/": {
        "keywords": [
            "deal analysis","cap rate","cash on cash return",
            "roi real estate","investment analysis"
        ],
        "priority": 4
    },
    "/types-of-mortgage/": {
        "keywords": [
            "mortgage types","fha vs conventional",
            "loan options","fixed vs arm","compare mortgages"
        ],
        "priority": 5
    },
    "/saving-for-your-home/": {
        "keywords": [
            "saving for a house","down payment savings",
            "budget for home purchase","how much to save for house"
        ],
        "priority": 4
    },
    "/form/": {
        "keywords": [
            "preapproval","apply for mortgage","start loan process",
            "get preapproved","loan application","talk to loan officer"
        ],
        "priority": 10
    },
    "/preapproval/": {
        "keywords": [
            "preapproval","get preapproved","mortgage approval",
            "qualify for mortgage","start application"
        ],
        "priority": 10
    }
}

LOW_PRIORITY = [
    "/privacy-policy/",
    "/terms-of-use/",
    "/ccpa-notice/",
    "/thank-you/"
]

def main():
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    updated = 0

    for page in data:
        url = page.get("url", "")
        record_updated = False

        # --- HIGH VALUE PATCHES ---
        for path, patch in PATCHES.items():
            if path in url:
                page["manual_keywords"] = patch["keywords"]
                page["priority"] = patch["priority"]
                record_updated = True

        # --- LOW VALUE PAGES ---
        for low in LOW_PRIORITY:
            if low in url:
                page["priority"] = 0

        # --- FHA CITY BOOST ---
        if "fha-loan-requirements" in url:
            city = url.split("/")[-2].replace("-", " ")
            page["manual_keywords"] = [
                f"fha loan {city}",
                f"fha requirements {city}",
                f"buy a house {city}",
                f"first time homebuyer {city}",
                f"low down payment {city}"
            ]
            page["priority"] = 6
            record_updated = True

        # --- AUTO FILL REMAINING ---
        if not page.get("manual_keywords"):
            slug_words = page.get("slug_keywords", [])
            extra = []

            if "calculator" in url:
                extra += ["calculate", "estimate", "payment", "monthly payment"]

            if "inspection" in url:
                extra += ["home inspection", "inspection process", "inspection checklist"]

            if "insurance" in url:
                extra += ["mortgage insurance", "pmi", "insurance cost"]

            if "afford" in url:
                extra += ["how much house can i afford", "affordability"]

            if "investment" in url:
                extra += ["investment property", "rental property", "real estate investing"]

            if "jumbo" in url:
                extra += ["jumbo loan", "high loan amount", "large mortgage"]

            if "hard-money" in url:
                extra += ["hard money loan", "fix and flip loan", "short term loan"]

            if "realtor" in url:
                extra += ["real estate agent", "choosing a realtor", "buyer agent"]

            if "refinance" in url:
                extra += ["refinance", "lower rate", "cash out refinance"]

            if "loan" in url:
                extra += ["mortgage loan", "home loan", "financing options"]

            page["manual_keywords"] = list(set(slug_words + extra))
            record_updated = True

        if record_updated:
            updated += 1

    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Updated pages: {updated}")


if __name__ == "__main__":
    main()
