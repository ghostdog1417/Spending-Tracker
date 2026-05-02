def _build_fallback_summary(data, total, category_totals):
    items = data.get("items", [])

    if not items:
        return "No spending insights are available because no receipt items were extracted locally."

    top_category = category_totals.idxmax() if not category_totals.empty else "Others"
    top_amount = float(category_totals.max()) if not category_totals.empty else float(total)
    average_spend = total / len(items) if items else 0
    top_item = max(items, key=lambda item: float(item.get("price", 0) or 0))
    top_item_name = str(top_item.get("name", "an item"))
    top_item_price = float(top_item.get("price", 0) or 0)

    return (
        f"You logged {len(items)} items totaling Rs. {total:.2f}. "
        f"The largest item was {top_item_name} at Rs. {top_item_price:.2f}. "
        f"Your highest spend was in {top_category} at Rs. {top_amount:.2f}, "
        f"with an average item cost of Rs. {average_spend:.2f}. "
        "Review the largest items first if you want the fastest way to trim spending."
    )


def generate_summary(data, total, category_totals):
    return _build_fallback_summary(data, total, category_totals)
