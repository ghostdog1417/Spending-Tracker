import pandas as pd


def process_data(data):
    items = data.get("items", [])
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue

        normalized_items.append(
            {
                "Item": item.get("name", "Unknown Item"),
                "Price": float(item.get("price", 0) or 0),
                "Category": item.get("category", "Others"),
            }
        )

    df = pd.DataFrame(normalized_items)

    if df.empty:
        return df, 0.0, pd.Series(dtype=float)

    df["Price"] = df["Price"].round(2)
    total = float(df["Price"].sum())
    category_totals = df.groupby("Category")["Price"].sum().sort_values(ascending=False)

    return df, total, category_totals
