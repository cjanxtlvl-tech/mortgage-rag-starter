import json
from collections import Counter

with open("data/veecasa_rag_qa_optimized.json") as f:
    data = json.load(f)

questions = [item["question"].lower() for item in data]
categories = [item.get("category", "unknown") for item in data]
links = [item.get("recommended_link") for item in data]

print("Total Qs:", len(questions))
print("Unique Qs:", len(set(questions)))
print("Categories:", Counter(categories))
print("Missing links:", sum(1 for l in links if not l))