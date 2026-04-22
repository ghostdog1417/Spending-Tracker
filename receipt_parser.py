import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ALLOWED_CATEGORIES = {"Food", "Travel", "Shopping", "Others"}


def _get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _extract_json_block(content):
    if not content:
        return ""

    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced_match:
        return fenced_match.group(1)

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return content[start : end + 1]

    return content


def _normalize_item(item):
    name = str(item.get("name") or item.get("item") or "Unknown Item").strip()

    raw_price = item.get("price", 0)
    if isinstance(raw_price, str):
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", raw_price)
        cleaned = match.group(0).replace(",", "") if match else ""
        price = float(cleaned) if cleaned else 0.0
    else:
        price = float(raw_price or 0)

    category = str(item.get("category") or "Others").strip().title()
    if category not in ALLOWED_CATEGORIES:
        category = "Others"

    return {"name": name, "price": round(price, 2), "category": category}


def _normalize_payload(payload):
    items = payload.get("items", [])
    normalized_items = [_normalize_item(item) for item in items if isinstance(item, dict)]
    return {"items": normalized_items}


def extract_receipt_data(image_bytes, mime_type="image/jpeg"):
    client = _get_client()
    if client is None:
        return {
            "error": "OpenAI API key not found.",
            "details": "Set OPENAI_API_KEY in your environment or .env file to analyze receipts.",
        }

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract receipt data. Return valid JSON with this shape only: "
                        '{"items":[{"name":"string","price":0,"category":"Food|Travel|Shopping|Others"}]}. '
                        "Use Others when unsure."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract each line item and its price from this receipt. "
                                "Ignore store metadata, taxes, totals, and payment details unless they are item lines."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_bytes}"}},
                    ],
                },
            ],
            max_tokens=1000,
        )
    except Exception as exc:
        return {
            "error": "Receipt analysis failed.",
            "details": str(exc),
        }

    content = response.choices[0].message.content
    json_block = _extract_json_block(content)

    try:
        parsed = json.loads(json_block)
    except json.JSONDecodeError:
        return {
            "error": "Could not parse the model response as JSON.",
            "raw": content,
        }

    return _normalize_payload(parsed)
