import os

from openai import OpenAI


def generate_grounded_answer(question: str, context: str) -> str:
    if not context.strip():
        return (
            "I could not find enough relevant mortgage information in the local knowledge base "
            "to answer that confidently."
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Add it to your environment before calling /ask.")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a mortgage Q&A assistant. "
        "Answer only using the provided context. "
        "If context is insufficient, clearly say you do not have enough grounded information. "
        "Be concise, conversational, and avoid repeating chunks verbatim."
    )
    user_prompt = (
        "Context:\n"
        f"{context}\n\n"
        "Question:\n"
        f"{question}\n\n"
        "Write a clean final answer for the user."
    )

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content if response.choices else None
    answer = (content or "").strip()
    if not answer:
        raise RuntimeError("The language model returned an empty answer.")
    return answer
