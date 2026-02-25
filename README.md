# Multimodal document parser (PDF tables -> CSV)

This project extracts tabular data from PDF documents and saves the result as CSV files.

It uses:
- OpenAI Responses API (vision) for table extraction
- schema-guided structured outputs using the provided schema files:
  - structure.json (json_schema format for Responses API)
  - structure.py (Pydantic models for validation)
- PyMuPDF to render PDF pages into high-resolution images before extraction

The output is validated against the schema before writing CSV, and the script includes a multi-run consistency test mode.

---


## Inputs

The script expects these files in the project root (same folder as the script):

- ibes_detail_history_docs_13.pdf
- ibes_summary_history_docs_14.pdf
- ibes_detail_history_docs_15.pdf
- structure.json
- structure.py
- course_api_key.txt  (not committed)

---

## Output

When you run the script, it produces 3 CSV files:

- hpaithan_ibes_detail_history_docs_13.csv
- hpaithan_ibes_summary_history_docs_14.csv
- hpaithan_ibes_detail_history_docs_15.csv

If you run in test mode (--test N), it also produces temporary run files:

- hpaithan_ibes_*.run1.csv, run2.csv, ...

If all runs match, the script keeps the final run as the official output CSV.

---

## Setup (uv + venv)

Requirements:
- uv installed
- Python installed (your local Python is fine)

From the project folder:

1) Create a virtual environment
uv venv .venv

2) Activate it (macOS / zsh)
source .venv/bin/activate

3) Install dependencies
uv pip install -r hpaithan_requirements.txt

Verify you are using the venv interpreter:
which python
python --version

---

## API key file (required)

Create a file named:
course_api_key.txt

Put your course API key in it as a single line:
sk-...

Important:
- do not commit this file
- do not paste the API key into code

The script expects the key at this path:
./course_api_key.txt

---

## Run

Normal run (generates the 3 output CSVs once):
python hpaithan_extract_tables.py

Alternative run command:
uv run hpaithan_extract_tables.py

---

## Consistency testing (recommended)

To verify extraction is stable across multiple runs:

python hpaithan_extract_tables.py --test 3

The script prints a sha256 hash per run so you can confirm identical output across runs.

If you see INCONSISTENT:
- increase the PDF render zoom inside the script (for clearer table images)
- rerun with --test 3 until consistent

---

## How extraction is enforced

The output format is schema-driven:
- structure.json is loaded and passed into Responses API as the text.format json_schema
- structure.py (Pydantic) validates the returned JSON before writing CSV

This ensures:
- the model returns data_records with strict required fields
- length/start/end are integers (as defined by the schema)
- malformed outputs fail fast with a clear error

---

## Notes about committing to GitHub safely

Use a .gitignore that excludes:
- course_api_key.txt
- .venv/
- __pycache__/
- generated CSVs
- screenshots

Example entries:
course_api_key.txt
.venv/
__pycache__/
*.csv
*.png

---

## Troubleshooting

1) "API key file not found"
- confirm course_api_key.txt exists in the same folder as the script
- confirm the script path is still ./course_api_key.txt

2) "Model did not return valid JSON" or "did not match schema"
- try increasing the render zoom (3.5 -> 4.0) in the PDF render function
- rerun in test mode to confirm stability

3) "Module not found"
- confirm venv is activated: you should see (.venv) in the prompt
- reinstall dependencies: uv pip install -r hpaithan_requirements.txt

---

## Tech stack

Python, OpenAI Responses API (vision), PyMuPDF, JSON Schema structured outputs, Pydantic
