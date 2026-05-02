# SmartSpend

SmartSpend is a Streamlit app that analyzes receipt images, extracts line items with local OCR, and summarizes spending by item and category.

## Features

- Upload a JPG, PNG, or JPEG receipt image.
- Extract receipt items locally with Tesseract OCR.
- View parsed items in a table.
- See a category breakdown chart.
- Get a quick spending summary based on the extracted data.

## Tech Stack

- Python
- Streamlit
- Plotly
- Pandas
- Pillow
- pytesseract
- Tesseract OCR

## Requirements

- Python 3.10 or newer.
- Tesseract OCR installed on your machine.
- Python packages from `requirements.txt`.

### Tesseract OCR

The app looks for Tesseract in one of these places:

- The `TESSERACT_CMD` environment variable.
- A `tesseract` executable available on your `PATH`.
- The default Windows install path: `C:\Program Files\Tesseract-OCR\tesseract.exe`.

If you need to point the app to a custom install, set `TESSERACT_CMD` before launching Streamlit.

## Setup

1. Create and activate a virtual environment.
2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

1. Install Tesseract OCR if it is not already installed.

## Run the app

Start the Streamlit app from the project root:

```bash
streamlit run app.py
```

Then open the local URL shown in the terminal, usually `http://localhost:8501`.

## How it works

1. Upload a receipt image.
2. The app extracts text from the image with OCR.
3. Receipt line items are normalized into a table and grouped by category.
4. A pie chart and summary are generated from the extracted data.

## Project Structure

- `app.py` - Streamlit UI and app flow.
- `receipt_parser.py` - OCR and receipt item extraction.
- `utils.py` - Data normalization and aggregation helpers.
- `summarizer.py` - Spending summary generation.
- `requirements.txt` - Python dependencies.
- `packages.txt` - System packages for environments that use it.

## Notes

- The OCR step is local, so receipt quality has a big impact on extraction accuracy.
- Clear, well-lit receipts with readable item lines work best.
