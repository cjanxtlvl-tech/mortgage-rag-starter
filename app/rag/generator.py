from openai import OpenAI
from app.config import get_settings


def generate_grounded_answer(question: str, context: str) -> str:
    if not context.strip():
        return (
            "I could not find enough relevant mortgage information in the local knowledge base "
            "to answer that confidently."
        )

    settings = get_settings()
    api_key = settings.openai_api_key.get_secret_value()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing from .env")

    model = settings.openai_model
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a mortgage advisor. "
        "Use the user's details, such as credit score and down payment, to personalize your response. "
        "Mention specific loan programs like FHA or conventional when relevant. "
        "Keep responses concise and conversational, focusing on key points. "
        "Ensure compliance-safe language. "
        "Avoid repetitive closings or sales-like language."
    )
    user_prompt = (
        "Context:\n"
        f"{context}\n\n"
        "Question:\n"
        f"{question}\n\n"
        "Craft a concise, personalized response with educational value. "
        "Limit to 2-4 short paragraphs or bullets. "
        "Do not add a call to action; the caller will add any final next-step language separately."
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
