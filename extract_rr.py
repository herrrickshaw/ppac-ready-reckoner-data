#!/usr/bin/env python3
"""Extract every table from a PPAC Ready Reckoner PDF into per-table CSVs.

Usage:
    python3 extract_rr.py <ready_reckoner.pdf> <out_subdir>

Strategy: these are PowerPoint-origin PDFs with real gridlines, so pdfplumber's
"lines" table strategy clusters cells reliably. We locate "Table X.Y : caption"
headings to name each CSV, extract tables page by page, join wrapped multi-line
header cells, and write an index.csv mapping table number -> caption -> page ->
file with row/col counts and a quality flag.
"""
import csv
import re
import sys
from pathlib import Path

import pdfplumber

# pdfplumber sometimes collapses spaces ("Table6.3(A):..."), so tolerate zero
# whitespace after "Table" and around the number/paren suffix.
CAP_RE = re.compile(r'Table\s*(\d+\.\d+\s*[A-Z]?\s*(?:\([A-Z]\))?)\s*[:：]\s*(.+)')
TS = {"vertical_strategy": "lines", "horizontal_strategy": "lines",
      "snap_tolerance": 4, "join_tolerance": 4}
FOOTER = re.compile(r'^(PPAC Ready Reckoner|Petroleum Planning|www\.ppac|\d+)\s*$', re.I)


def slug(s):
    s = re.sub(r'\(Figures?.*?\)', '', s)
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower()
    return s[:48]


def tno(s):
    return re.sub(r'\s+', '', s)          # "6.3 (A)" -> "6.3(A)"


def clean(cell):
    if cell is None:
        return ''
    return re.sub(r'\s+', ' ', str(cell).replace('\n', ' ')).strip()


def table_ok(t):
    """Keep tables that look like data: >=2 rows, >=2 cols, mostly non-empty."""
    if not t or len(t) < 2 or len(t[0]) < 2:
        return False
    cells = [c for row in t for c in row]
    nonempty = sum(1 for c in cells if clean(c))
    return nonempty >= max(4, 0.35 * len(cells))


def main():
    pdf_path = Path(sys.argv[1])
    out = Path(__file__).resolve().parent / sys.argv[2]
    (out / "csv").mkdir(parents=True, exist_ok=True)

    index = []
    used_names = {}
    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            caps = [(tno(m.group(1)), clean(m.group(2))[:90])
                    for m in (CAP_RE.match(l.strip()) for l in text.splitlines()) if m]
            try:
                tables = [t for t in page.extract_tables(TS) if table_ok(t)]
            except Exception as e:
                tables = []
                index.append({"table_no": "", "caption": f"(extract error: {e})",
                              "page": pi, "csv_file": "", "rows": 0, "cols": 0, "flag": "error"})
                continue

            # Caption-only pages (charts/figures) still get logged.
            if caps and not tables:
                for no, cap in caps:
                    index.append({"table_no": no, "caption": cap, "page": pi,
                                  "csv_file": "", "rows": 0, "cols": 0, "flag": "figure/no-grid"})
                continue

            for ti, t in enumerate(tables):
                if ti < len(caps):
                    no, cap = caps[ti]
                    base = f"Table_{no}_{slug(cap)}"
                elif caps:                       # more tables than captions: attach to last caption
                    no, cap = caps[-1]
                    base = f"Table_{no}_{slug(cap)}_part{ti}"
                else:                            # continuation of a table from a previous page
                    no, cap, base = "", "(continuation / no caption on page)", f"p{pi:03d}_cont{ti}"
                name = base
                k = used_names.get(base, 0)
                if k:
                    name = f"{base}__{k+1}"
                used_names[base] = k + 1

                rows = [[clean(c) for c in row] for row in t]
                (out / "csv" / f"{name}.csv").write_text("")
                with (out / "csv" / f"{name}.csv").open("w", newline="") as f:
                    csv.writer(f).writerows(rows)
                index.append({"table_no": no, "caption": cap, "page": pi,
                              "csv_file": f"csv/{name}.csv", "rows": len(rows),
                              "cols": len(rows[0]) if rows else 0, "flag": "ok"})

    index.sort(key=lambda r: (r["page"],))
    with (out / "index.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["table_no", "caption", "page", "csv_file", "rows", "cols", "flag"])
        w.writeheader(); w.writerows(index)

    ok = sum(1 for r in index if r["flag"] == "ok")
    fig = sum(1 for r in index if r["flag"].startswith("figure"))
    print(f"{pdf_path.name}: {ok} tables -> {out}/csv/  ({fig} figures/charts logged, no grid)")
    print(f"index: {out}/index.csv")


if __name__ == "__main__":
    main()
