# PPAC Ready Reckoner — tables as CSV

Machine-readable extracts of the tables in the Petroleum Planning & Analysis Cell (PPAC, Ministry of
Petroleum & Natural Gas, India) *Ready Reckoner* PDF, plus the small `pdfplumber` script that produced them.
Domain: Indian oil, gas, LPG, CNG, refining, pricing, taxation and subsidy statistics. Output artefacts: one
CSV per table and an `index.csv` that maps table number → caption → PDF page → file.

> Status: archived snapshot (data-only plus one extraction script). Figures are PPAC's own, reproduced as
> extracted; no cleaning or re-typing was done, so check cell values against the source PDF before relying
> on them. Not investment advice.

<!-- how-to-use-with-ai -->
> **New here?** See [How to use this repo with AI (Claude, Gemini, ChatGPT)](HOW_TO_USE_WITH_AI.md) — clone it, paste it into an AI tool, and ask in plain English.

## What it does
- `annual_fy2025-26_h1/csv/` holds 100 CSV files extracted from the Ready Reckoner edition whose tables are dated "as on 01.10.2025" (H1 of FY2025-26), spanning PDF pages 4–123.
- `annual_fy2025-26_h1/index.csv` lists every extracted table with `table_no`, `caption`, `page`, `csv_file`, `rows`, `cols`, `flag` (all 100 rows are `flag=ok`).
- `extract_rr.py` re-runs the extraction on any Ready Reckoner PDF: it finds `Table X.Y : caption` headings to name files, pulls gridline tables page by page with `pdfplumber`, and writes the index.
- Tables that continue onto a page without a caption are saved as `pNNN_contK.csv` and listed with an empty `table_no`.

## Quick start
```bash
git clone https://github.com/herrrickshaw/ppac-ready-reckoner-data.git
cd ppac-ready-reckoner-data
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 extract_rr.py <ready_reckoner.pdf> annual_fy2025-26_h1   # writes <out_subdir>/csv/*.csv and index.csv
```
The PDF itself is not in the repo; download the current Ready Reckoner from https://ppac.gov.in and pass its path.
Just reading the data needs no install — open the CSVs directly.

## How it works
| Stage | Where | Output |
|---|---|---|
| Find captions on each page (`CAP_RE`, tolerant of pdfplumber dropping spaces: `Table6.3(A):`) | `extract_rr.py` | `(table_no, caption)` list per page |
| Extract tables with the `lines` strategy (`snap_tolerance`/`join_tolerance` 4) | `extract_rr.py` → `pdfplumber` | raw cell grids |
| Keep only grids that look like data: ≥2 rows, ≥2 cols, ≥4 and ≥35 % non-empty cells (`table_ok`) | `extract_rr.py` | filtered tables |
| Name files `Table_<no>_<slug>.csv`; extra tables on a page get `_partK`, repeats get `__2`, caption-less pages get `pNNN_contK` | `extract_rr.py` | `csv/*.csv` |
| Log caption-only pages (charts) as `figure/no-grid`, page errors as `error`, write `index.csv` sorted by page | `extract_rr.py` | `index.csv` |

Design note: the Ready Reckoner is a PowerPoint-origin PDF with real gridlines, so the `lines` strategy clusters
cells reliably; no OCR is needed for this edition.

## Repository layout
| Path | Purpose |
|---|---|
| `extract_rr.py` | PDF → CSV extraction script (CLI: `<pdf> <out_subdir>`) |
| `requirements.txt` | `pdfplumber`, the only runtime dependency of the script |
| `requirements-ocr.txt` | `pymupdf` + `requests` for an opt-in remote OCR fallback (`UNLIMITED_OCR_URL`); **not used by `extract_rr.py`** — kept for scanned editions |
| `annual_fy2025-26_h1/index.csv` | table catalogue for the extracted edition (tracked) |
| `annual_fy2025-26_h1/csv/` | 100 per-table CSVs (tracked data) |
| `HOW_TO_USE_WITH_AI.md` | plain-language guide for non-programmers |
| `CLAUDE.md` | agent guidance (source-fetching rules) |

## Data sources
| Source | What is taken | Access route | Licence / caveat |
|---|---|---|---|
| PPAC Ready Reckoner (https://ppac.gov.in) | every gridline table in the PDF | manual download, then `extract_rr.py` | Government of India publication; cell text is reproduced verbatim from the PDF. Header rows that wrapped in the PDF may appear joined or split; multi-level headers are flattened as pdfplumber sees them. |

## Configuration
None. There are no environment variables or secrets; `extract_rr.py` takes the PDF path and output
sub-directory as positional arguments and writes next to itself.

## Testing
```bash
python -m py_compile extract_rr.py
python3 extract_rr.py <ready_reckoner.pdf> /tmp/rr_check && diff -r /tmp/rr_check annual_fy2025-26_h1   # should be empty for the same PDF
```
There is no test suite.

## Limitations and known issues
- Only one edition (`annual_fy2025-26_h1`) is tracked; the source PDF is not committed.
- Caption matching is positional: when a page has more tables than captions the extras are attached to the last caption (`_partK`), which can mislabel a stray grid.
- Continuation pages (`pNNN_contK.csv`, 18 files in this edition) carry no caption; use the preceding table in `index.csv` to identify them.
- Numbers keep the PDF's formatting (thousands separators, footnote markers, `*`); parse them before arithmetic.
- `extract_rr.py` has no argument validation — running it without two arguments raises `IndexError`.

## Licence
No licence file yet — all rights reserved for the script; the underlying statistics are PPAC's.
