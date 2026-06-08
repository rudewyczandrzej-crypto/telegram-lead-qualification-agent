import os, json
from pathlib import Path
from groq import Groq

MODEL_NAME = "llama-3.3-70b-versatile"


def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY не знайдено у Railway Variables")
    return Groq(api_key=api_key)


def clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text.replace("```json", "", 1).strip()
    if text.startswith("```"):
        text = text.replace("```", "", 1).strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def read_config():
    path = Path("business_config.md")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def process_lead_message(lead: dict, messages: list[dict], user_message: str) -> dict:
    config = read_config()
    history = [{"role": m["role"], "message": m["message"]} for m in messages[-10:]]

    system = """
You are an AI lead qualification agent.

Your job:
- Ask one useful follow-up question at a time.
- Extract lead fields from conversation.
- Score lead from 0 to 100.
- Decide if lead is weak, medium, or strong.
- Do not be pushy.
- If enough data is collected, set is_complete=true.
- Return only valid JSON.

JSON format:
{
  "reply": "message to user",
  "extracted": {
    "name": null,
    "email": null,
    "phone": null,
    "company": null,
    "need": null,
    "service_type": null,
    "budget": null,
    "timeline": null,
    "decision_maker": null
  },
  "lead_score": 0,
  "quality": "weak | medium | strong",
  "is_complete": true or false,
  "ai_summary": "short lead summary"
}
"""

    prompt = json.dumps({
        "business_config": config,
        "current_lead": dict(lead) if lead else {},
        "history": history,
        "new_user_message": user_message,
    }, ensure_ascii=False, indent=2)

    client = get_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0.3,
    )

    raw = clean_json(response.choices[0].message.content)
    try:
        return json.loads(raw)
    except Exception:
        return {
            "reply": "Дякую! Розкажіть, будь ласка, трохи детальніше про вашу потребу, бюджет і дедлайн.",
            "extracted": {},
            "lead_score": 0,
            "quality": "medium",
            "is_complete": False,
            "ai_summary": raw[:500],
        }


def generate_sales_brief(lead: dict, messages: list[dict]) -> str:
    history = "\n".join([f"{m['role']}: {m['message']}" for m in messages])
    prompt = f"""
Create a short sales brief for this lead.

Lead:
{dict(lead)}

Conversation:
{history}

Return practical bullet points:
- lead summary
- need
- budget/timeline
- score/quality
- next action
"""

    client = get_client()
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "You are a sales operations assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content
