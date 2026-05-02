import base64
import io
import re

from PIL import Image, ImageFilter, ImageOps

try:
    import pytesseract
except Exception:  # pragma: no cover - optional local dependency
    pytesseract = None

ALLOWED_CATEGORIES = {"Food", "Travel", "Shopping", "Others"}

CATEGORY_KEYWORDS = {
    "Food": ("burger", "pizza", "coffee", "tea", "lunch", "dinner", "breakfast", "meal", "snack", "restaurant", "cafe", "food"),
    "Travel": ("uber", "ola", "taxi", "cab", "bus", "train", "metro", "fuel", "petrol", "diesel", "travel", "fare"),
    "Shopping": ("store", "mall", "shop", "market", "clothes", "shirt", "pant", "jeans", "shoes", "shopping"),
}

IGNORED_LINE_KEYWORDS = (
    "subtotal",
    "total",
    "grand total",
    "tax",
    "vat",
    "gst",
    "service charge",
    "change",
    "balance",
    "cash",
    "card",
    "payment",
    "amount due",
    "amount paid",
    "discount",
    "tip",
)


def _decode_image(image_payload):
    try:
        raw_bytes = base64.b64decode(image_payload)
        return Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    except Exception:
        return None


def _preprocess_image(image):
    grayscale = ImageOps.grayscale(image)
    grayscale = ImageOps.autocontrast(grayscale)
    grayscale = grayscale.filter(ImageFilter.SHARPEN)

    if min(grayscale.size) < 1200:
        grayscale = grayscale.resize((grayscale.width * 2, grayscale.height * 2))

    return grayscale


def _extract_text(image):
    if pytesseract is None:
        return ""

    try:
        return pytesseract.image_to_string(_preprocess_image(image), config="--psm 6")
    except Exception:
        return ""


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


def _classify_category(text):
    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "Others"


def _clean_name(raw_name):
    name = re.sub(r"\s+", " ", raw_name or "").strip(" -:|,")
    name = re.sub(r"\b(?:qty|quantity|x)\s*\d+\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", name).strip(" -:|,")
    return name or "Unknown Item"


def _is_noise_line(line):
    if not line:
        return True

    lowered = line.lower()
    if any(keyword in lowered for keyword in IGNORED_LINE_KEYWORDS):
        return True

    alnum_count = len(re.sub(r"[^a-z0-9]", "", lowered))
    return alnum_count < 2


def _parse_line_items(text):
    items = []
    if not text:
        return items

    price_pattern = re.compile(r"(?:rs\.?\s*)?(\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE)

    for line in text.splitlines():
        cleaned_line = re.sub(r"\s+", " ", line).strip(" -:|,")
        if _is_noise_line(cleaned_line):
            continue

        matches = list(price_pattern.finditer(cleaned_line))
        if not matches:
            continue

        price_match = matches[-1]
        raw_name = cleaned_line[:price_match.start()]
        name = _clean_name(raw_name)

        try:
            price = float(price_match.group(1).replace(",", ""))
        except ValueError:
            continue

        if not name or name.replace(" ", "").isdigit():
            name = "Unknown Item"

        items.append(
            {
                "name": name,
                "price": round(price, 2),
                "category": _classify_category(cleaned_line),
            }
        )

    return items


def extract_receipt_data(image_bytes, mime_type="image/jpeg"):
    image = _decode_image(image_bytes)
    if image is None:
        return {
            "error": "Could not read the uploaded receipt image.",
            "details": "Upload a valid JPG or PNG receipt image and try again.",
        }

    text = _extract_text(image)
    items = _parse_line_items(text)

    if not items:
        return {
            "error": "Could not extract line items locally.",
            "details": (
                "Install pytesseract and the Tesseract OCR engine for better local receipt recognition, "
                "then upload a clearer receipt image."
            ),
        }

    return _normalize_payload({"items": items})
