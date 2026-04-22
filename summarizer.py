import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def _build_fallback_summary(data, total, category_totals):
    items = data.get("items", [])

    if not items:
        return "No spending insights are available because no receipt items were extracted."

    top_category = category_totals.idxmax() if not category_totals.empty else "Others"
    top_amount = float(category_totals.max()) if not category_totals.empty else float(total)
    average_spend = total / len(items) if items else 0

    return (
        f"You logged {len(items)} items totaling Rs. {total:.2f}. "
        f"Your highest spend was in {top_category} at Rs. {top_amount:.2f}, "
        f"with an average item cost of Rs. {average_spend:.2f}. "
        "Review the largest items first if you want the fastest way to trim spending."
    )


def generate_summary(data, total, category_totals):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return _build_fallback_summary(data, total, category_totals)

    client = OpenAI(api_key=api_key)
    prompt = f"""
    Here is expense data:
    {data}

    The total spend is Rs. {total:.2f}.
    Category totals: {category_totals.to_dict() if not category_totals.empty else {}}

    Write a short and practical financial summary in 3 sentences or fewer.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return _build_fallback_summary(data, total, category_totals)
