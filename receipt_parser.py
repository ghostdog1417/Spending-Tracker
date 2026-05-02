import base64
import io
import os
import re
import shutil

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

NON_ITEM_HINTS = (
    "invoice",
    "bill no",
    "bill#",
    "receipt",
    "date",
    "time",
    "server",
    "cashier",
    "table",
    "token",
    "gstin",
    "customer",
    "phone",
    "address",
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

    configured_path = os.getenv("TESSERACT_CMD")
    detected_path = shutil.which("tesseract")
    default_windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    if configured_path:
        pytesseract.pytesseract.tesseract_cmd = configured_path
    elif detected_path:
        pytesseract.pytesseract.tesseract_cmd = detected_path
    elif os.path.exists(default_windows_path):
        pytesseract.pytesseract.tesseract_cmd = default_windows_path

    try:
        return pytesseract.image_to_string(_preprocess_image(image), config="--psm 6")
    except Exception:
        return ""


def _is_tesseract_available():
    if pytesseract is None:
        return False

    configured_path = os.getenv("TESSERACT_CMD")
    detected_path = shutil.which("tesseract")
    default_windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    return bool(
        (configured_path and os.path.exists(configured_path))
        or detected_path
        or os.path.exists(default_windows_path)
    )


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


def _normalize_ocr_line(line):
    compact = re.sub(r"\s+", " ", line or "").strip()
    compact = re.sub(r"[|]", " ", compact)
    compact = re.sub(r"[.]{2,}", " ", compact)
    compact = re.sub(r"\s+", " ", compact).strip(" -:|,")
    return compact


def _clean_name(raw_name):
    name = _normalize_ocr_line(raw_name)
    name = re.sub(r"[₹$€£]", "", name)
    name = re.sub(r"\b(?:rs|inr|mrp|amt|price)\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^(?:\d+\s*[xX]\s+)", "", name)
    name = re.sub(r"\b(?:qty|quantity)\s*[:.]?\s*\d+\b", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\b\d+\s*[xX]\b", "", name)
    name = re.sub(r"\b[a-zA-Z]{0,2}\d{4,}\b", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -:|,")
    return name or "Unknown Item"


def _is_noise_line(line):
    if not line:
        return True

    lowered = line.lower()
    if any(keyword in lowered for keyword in IGNORED_LINE_KEYWORDS):
        return True

    if any(hint in lowered for hint in NON_ITEM_HINTS):
        return True

    if re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", lowered):
        return True

    if re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", lowered):
        return True

    alnum_count = len(re.sub(r"[^a-z0-9]", "", lowered))
    return alnum_count < 2


def _extract_line_price(line):
    # Prioritize amounts near the end of the line where receipt prices usually appear.
    tail_match = re.search(
        r"(?:rs\.?|inr|mrp|amt|price)?\s*[₹$]?\s*(\d{1,6}(?:[.,]\d{2})?)\s*$",
        line,
        re.IGNORECASE,
    )
    if tail_match:
        return tail_match.group(1), tail_match.start(1)

    fallback_matches = list(re.finditer(r"(\d{1,6}(?:[.,]\d{2})?)", line))
    if not fallback_matches:
        return None, -1

    chosen = fallback_matches[-1]
    return chosen.group(1), chosen.start(1)


def _parse_price_value(raw_price):
    value = (raw_price or "").strip()
    if not value:
        return None

    if "," in value and "." in value:
        # Assume commas are thousands separators when both are present.
        normalized = value.replace(",", "")
    elif "," in value:
        left, right = value.rsplit(",", 1)
        if right.isdigit() and len(right) == 2:
            normalized = f"{left}.{right}"
        else:
            normalized = value.replace(",", "")
    else:
        normalized = value

    try:
        return float(normalized)
    except ValueError:
        return None


def _parse_line_items(text):
    items = []
    seen = set()
    if not text:
        return items

    for line in text.splitlines():
        cleaned_line = _normalize_ocr_line(line)
        if _is_noise_line(cleaned_line):
            continue

        raw_price, price_start = _extract_line_price(cleaned_line)
        if not raw_price:
            continue

        raw_name = cleaned_line[:price_start]
        name = _clean_name(raw_name)

        price = _parse_price_value(raw_price)
        if price is None:
            continue

        if price <= 0:
            continue

        if price > 50000:
            continue

        if not name or name.replace(" ", "").isdigit():
            name = "Unknown Item"

        fingerprint = (name.lower(), round(price, 2))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

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
        if not _is_tesseract_available():
            details = (
                "Install pytesseract and the Tesseract OCR engine for better local receipt recognition, "
                "then restart the app."
            )
        else:
            details = "OCR ran, but no line items were detected. Upload a clearer, well-lit receipt image and try again."

        return {
            "error": "Could not extract line items locally.",
            "details": details,
        }

    return _normalize_payload({"items": items})
