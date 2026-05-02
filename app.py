import base64

import plotly.express as px
import streamlit as st

from receipt_parser import extract_receipt_data
from summarizer import generate_summary
from utils import process_data


st.set_page_config(page_title="SmartSpend", layout="wide")

st.title("SmartSpend - Receipt Analyzer")
st.caption("Upload a receipt image to extract items locally, organize expenses, and get a quick spending summary.")

with st.sidebar:
    st.header("How it works")
    st.write("1. Upload a clear JPG or PNG receipt image.")
    st.write("2. SmartSpend extracts item names, prices, and categories using local OCR.")
    st.write("3. Review totals, category breakdown, and spending insights.")

uploaded_file = st.file_uploader("Upload your receipt", type=["jpg", "png", "jpeg"])

if not uploaded_file:
    st.info("Add a receipt image to begin.")
    st.stop()

image_bytes = uploaded_file.getvalue()
encoded_image = base64.b64encode(image_bytes).decode("utf-8")

st.image(image_bytes, caption="Uploaded Receipt", use_container_width=True)

with st.spinner("Analyzing receipt..."):
    data = extract_receipt_data(encoded_image, uploaded_file.type or "image/jpeg")

if "error" in data:
    st.error(data["error"])
    if data.get("details"):
        st.caption(data["details"])
    if data.get("raw"):
        with st.expander("Model output"):
            st.code(data["raw"], language="json")
    st.stop()

df, total, category_totals = process_data(data)

if df.empty:
    st.warning("No line items were extracted from this receipt. Try a clearer image or another receipt.")
    st.stop()

metric_col, count_col = st.columns(2)
metric_col.metric("Total Spending", f"Rs. {total:.2f}")
count_col.metric("Items Found", len(df))

st.subheader("Extracted Items")
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("Category Breakdown")

if category_totals.empty:
    st.info("No category totals were available for charting.")
else:
    fig = px.pie(
        names=category_totals.index,
        values=category_totals.values,
        title="Spending Distribution",
        hole=0.35,
    )
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("AI Summary")
st.info(generate_summary(data, total=total, category_totals=category_totals))
