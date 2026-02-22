#!/usr/bin/env python3
"""
Responses API PDF table extraction -> CSV

REQUIRED:
- Uses Responses API
- Uses provided schema files: structure.json + structure.py
- Includes python --version output below
- Includes path where course API key is expected


# python --version
# Python 3.13.2
"""

import base64
import csv
import hashlib
import json
import os
import sys
from typing import List, Dict, Any, Tuple

import fitz  # PyMuPDF
from openai import OpenAI

# import the Pydantic models from structure.py (must be in same folder)
from structure import DataExtractionResponse



USERNAME = "hpaithan"  


COURSE_API_KEY_PATH = "./course_api_key.txt"


STRUCTURE_JSON_PATH = "./structure.json"


# INPUT / OUTPUT

PDF_JOBS = [
    {"pdf_path": "./ibes_detail_history_docs_13.pdf", "out_csv": f"./{USERNAME}_ibes_detail_history_docs_13.csv"},
    {"pdf_path": "./ibes_summary_history_docs_14.pdf", "out_csv": f"./{USERNAME}_ibes_summary_history_docs_14.csv"},
    {"pdf_path": "./ibes_detail_history_docs_15.pdf", "out_csv": f"./{USERNAME}_ibes_detail_history_docs_15.csv"},
]

CSV_HEADER = ["file_name", "key", "item", "data_type", "format", "length", "start", "end", "comments"]


MODEL = "gpt-5-nano"


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def read_api_key(path: str) -> str:
    if not os.path.exists(path):
        die(f"API key file not found at: {path}\nCreate it with your course key on a single line.")
    key = open(path, "r", encoding="utf-8").read().strip()
    if not key or " " in key or not key.startswith("sk-"):
        die("API key file exists but does not look valid. It must be one line like: sk-...")
    return key


def load_schema_format(structure_json_path: str) -> Dict[str, Any]:
    """
    Loads structure.json and returns the exact object to plug into:
    resp = client.responses.create(..., text=<RETURNED_OBJECT>)
    """
    if not os.path.exists(structure_json_path):
        die(f"Missing schema file: {structure_json_path}")
    data = json.load(open(structure_json_path, "r", encoding="utf-8"))
    if "format" not in data:
        die("structure.json must contain a top-level key named 'format'")
    return data["format"]


def pdf_page_to_image_data_url(pdf_path: str, page_index: int = 0, zoom: float = 3.5) -> str:
    """
    Render a PDF page to a high-resolution PNG and return a base64 data URL.
    zoom 3.5-4.0 usually improves table stability.
    """
    if not os.path.exists(pdf_path):
        die(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    if doc.page_count <= page_index:
        die(f"PDF {pdf_path} does not have page index {page_index}")

    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def call_responses_extract(
    client: OpenAI,
    schema_format: Dict[str, Any],
    image_data_url: str,
    source_pdf_name: str,
) -> DataExtractionResponse:
    """
    Calls the Responses API and returns a validated DataExtractionResponse (Pydantic).
    Uses the exact schema from structure.json.
    """

    instructions = f"""
You are extracting tabular data from a PDF page screenshot.

Return JSON that matches the provided schema EXACTLY:
- Top-level key: data_records (array)
- Each record must have:
  file_name (string), key (string), item (string), data_type (string), format (string),
  length (integer), start (integer), end (integer), comments (string)

Rules:
- Extract ALL table rows visible on the page, top-to-bottom.
- Do NOT invent rows.
- Preserve text exactly as shown (case/punctuation).
- IMPORTANT: length/start/end must be integers (no quotes).
- If a comments cell is blank, use "na".
- file_name must be exactly: {source_pdf_name}
"""

    resp = client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": instructions.strip()}]},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Extract every table row from this page."},
                    {"type": "input_image", "image_url": image_data_url, "detail": "high"},
                ],
            },
        ],
        text={"format": schema_format},
    )

    # With json_schema enabled, output_text should be valid JSON.
    raw = resp.output_text
    try:
        parsed = json.loads(raw)
    except Exception as e:
        die(f"Model did not return valid JSON: {e}\nRaw output:\n{raw}")

    # Validate using the Pydantic model from structure.py
    try:
        validated = DataExtractionResponse.model_validate(parsed)
    except Exception as e:
        die(f"JSON did not match structure.py schema: {e}\nParsed JSON:\n{json.dumps(parsed, indent=2)}")

    return validated


def write_csv(out_path: str, data: DataExtractionResponse) -> None:
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for r in data.data_records:
            w.writerow(
                {
                    "file_name": r.file_name,
                    "key": r.key,
                    "item": r.item,
                    "data_type": r.data_type,
                    "format": r.format,
                    "length": r.length,
                    "start": r.start,
                    "end": r.end,
                    "comments": r.comments,
                }
            )


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run_once(client: OpenAI, schema_format: Dict[str, Any], pdf_path: str, out_csv: str) -> Tuple[str, int]:
    pdf_base = os.path.basename(pdf_path)
    img = pdf_page_to_image_data_url(pdf_path, page_index=0, zoom=3.5)
    extracted = call_responses_extract(client, schema_format, img, source_pdf_name=pdf_base)
    write_csv(out_csv, extracted)
    return sha256_file(out_csv), len(extracted.data_records)


def main():
    api_key = read_api_key(COURSE_API_KEY_PATH)
    schema_format = load_schema_format(STRUCTURE_JSON_PATH)

    client = OpenAI(api_key=api_key)

    # Optional: consistency test mode
    # python script.py --test 3
    test_runs = 1
    if len(sys.argv) == 3 and sys.argv[1] == "--test":
        try:
            test_runs = int(sys.argv[2])
        except:
            die("Usage: python <script>.py --test 3")

    print(f"MODEL: {MODEL}")
    print(f"API KEY PATH: {COURSE_API_KEY_PATH}")
    print(f"SCHEMA PATH: {STRUCTURE_JSON_PATH}")
    print(f"TEST RUNS PER PDF: {test_runs}")
    print("-" * 60)

    for job in PDF_JOBS:
        pdf_path = job["pdf_path"]
        out_csv = job["out_csv"]

        print(f"PDF: {pdf_path}")

        if test_runs == 1:
            sha, nrows = run_once(client, schema_format, pdf_path, out_csv)
            print(f"  wrote: {out_csv}")
            print(f"  rows: {nrows}")
            print(f"  sha256: {sha[:16]}...")
        else:
            hashes = []
            row_counts = []
            tmp_files = []

            for i in range(test_runs):
                tmp_out = out_csv.replace(".csv", f".run{i+1}.csv")
                sha, nrows = run_once(client, schema_format, pdf_path, tmp_out)
                hashes.append(sha)
                row_counts.append(nrows)
                tmp_files.append(tmp_out)
                print(f"  run {i+1}: {os.path.basename(tmp_out)} rows={nrows} sha256={sha[:16]}...")

            if len(set(hashes)) == 1:
                # move last run into the official output name
                os.replace(tmp_files[-1], out_csv)
                print("  CONSISTENT ✅")
                print(f"  final saved as: {out_csv}")
                # keep earlier run files if you want, or delete them:
                # for p in tmp_files[:-1]:
                #     os.remove(p)
            else:
                print("  INCONSISTENT ❌ (hashes differ)")
                print(f"  row_counts: {row_counts}")
                print("  Keep the .run*.csv files while you tune zoom/model/prompt.")

        print("-" * 60)

    print("Done.")


if __name__ == "__main__":
    main()