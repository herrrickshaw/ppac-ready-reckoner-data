import csv
import sys

import pytest

from conftest import FakePage


# ── caption regex ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("line,no,cap", [
    ("Table 1.1 : Crude Oil Production", "1.1 ", "Crude Oil Production"),
    ("Table6.3(A): LPG Sales", "6.3(A)", "LPG Sales"),
    ("Table 6.3 (B) : Mixed", "6.3 (B)", "Mixed"),
    ("Table 2.10B： full-width colon", "2.10B", "full-width colon"),
    ("table 3.2: lowercase t is not a caption", None, None),
    ("Table A: no number", None, None),
    ("See Table 1.1 : not at line start", None, None),
])
def test_caption_regex(rr, line, no, cap):
    m = rr.CAP_RE.match(line)
    if no is None:
        assert m is None
    else:
        assert m.group(1) == no and m.group(2) == cap


def test_tno_normalises_whitespace(rr):
    assert rr.tno("6.3 (A)") == "6.3(A)" and rr.tno("1.1 ") == "1.1" and rr.tno("2.1\tB") == "2.1B"


def test_slug(rr):
    assert rr.slug("Crude Oil Production (Figures in MMT)") == "crude_oil_production"
    assert rr.slug("Price (Figure in Rs/litre) of petrol & diesel") == "price_of_petrol_diesel"
    assert rr.slug("  --Weird // Caption!!  ") == "weird_caption"
    assert rr.slug("x" * 100) == "x" * rr.SLUG_MAX_LEN == "x" * 48
    assert rr.slug("é ü") == ""


def test_clean(rr):
    assert rr.clean(None) == ""
    assert rr.clean("  a\n b\t\tc  ") == "a b c"
    assert rr.clean(12.5) == "12.5" and rr.clean(0) == "0"


def grid(n_rows, n_cols, filled):
    cells = [["x" if (r * n_cols + c) < filled else None for c in range(n_cols)] for r in range(n_rows)]
    return cells


@pytest.mark.parametrize("t,ok", [
    (None, False), ([], False),
    ([["a", "b"]], False),                        # one row
    ([["a"], ["b"]], False),                      # one column
    (grid(2, 2, 4), True),                        # 4 of 4 cells: meets MIN_NONEMPTY_CELLS exactly
    (grid(2, 2, 3), False),                       # 3 filled < 4 minimum
    (grid(4, 5, 7), True),                        # 7 of 20 = 35% exactly
    (grid(4, 5, 6), False),                       # 6 of 20 = 30% < 35% (and below the max())
    (grid(3, 4, 4), False),                       # 4 filled but 4/12 = 33% < 35%
    ([["", " ", "\n"], ["", "x", "y"], ["a", "b", "c"]], True),   # blank/whitespace cells do not count
    ([["", " "], ["\n", None]], False),
])
def test_table_ok(rr, t, ok):
    assert rr.table_ok(t) is ok


def test_constants(rr):
    assert (rr.MIN_NONEMPTY_CELLS, rr.MIN_NONEMPTY_FRAC, rr.CAPTION_MAX_LEN) == (4, 0.35, 90)
    assert rr.TS["vertical_strategy"] == "lines" and rr.TS["snap_tolerance"] == 4


# ── main ─────────────────────────────────────────────────────────────────────
def good(cols=3, rows=3, tag="v"):
    return [[f"{tag}{r}{c}" for c in range(cols)] for r in range(rows)]


def run(rr, tmp_path, monkeypatch, capsys, pages, name="rr.pdf"):
    rr.fake.pages = pages
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["extract_rr.py", str(tmp_path / name), str(out)])
    rr.main()
    index = list(csv.DictReader(open(out / "index.csv")))
    return out, index, capsys.readouterr().out


def test_named_tables_index_and_summary(rr, tmp_path, monkeypatch, capsys):
    t = [[" Item \n name", "FY 2024-25", None], ["Crude", "1,000", "x"], ["LPG", "2,000", "y"]]
    pages = [FakePage("PPAC Ready Reckoner\nTable 1.1 : Crude Oil Production (Figures in MMT)\n", [t])]
    out, index, text = run(rr, tmp_path, monkeypatch, capsys, pages)
    name = "Table_1.1_crude_oil_production"
    assert [r["csv_file"] for r in index] == [f"csv/{name}.csv"]
    assert index[0] == {"table_no": "1.1", "caption": "Crude Oil Production (Figures in MMT)", "page": "1",
                        "csv_file": f"csv/{name}.csv", "rows": "3", "cols": "3", "flag": "ok"}
    rows = list(csv.reader(open(out / "csv" / f"{name}.csv")))
    assert rows[0] == ["Item name", "FY 2024-25", ""]                 # cells are cleaned and None -> ''
    assert rows[2] == ["LPG", "2,000", "y"]
    assert list(csv.reader(open(out / "index.csv")))[0] == rr.INDEX_FIELDS
    assert "rr.pdf: 1 tables ->" in text and "(0 figures/charts logged, no grid)" in text
    assert str(tmp_path / "rr.pdf") in [str(p) for p in rr.fake.opened]
    assert pages[0].seen_settings == rr.TS


def test_caption_only_page_is_logged_as_a_figure(rr, tmp_path, monkeypatch, capsys):
    pages = [FakePage("Table 2.1 : Refinery Chart\nTable 2.2: Another Chart", [])]
    out, index, text = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert [(r["table_no"], r["flag"], r["csv_file"], r["rows"]) for r in index] == [
        ("2.1", "figure/no-grid", "", "0"), ("2.2", "figure/no-grid", "", "0")]
    assert "0 tables" in text and "(2 figures/charts logged, no grid)" in text
    assert not list((out / "csv").iterdir())


def test_junk_grids_are_filtered_before_naming(rr, tmp_path, monkeypatch, capsys):
    junk = [["", ""], ["", ""]]
    pages = [FakePage("Table 3.1 : Only Junk", [junk]), FakePage("Table 3.2 : Mixed", [junk, good()])]
    out, index, _ = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert [(r["page"], r["flag"]) for r in index] == [("1", "figure/no-grid"), ("2", "ok")]   # page 1: the junk grid is not a table
    assert index[1]["csv_file"] == "csv/Table_3.2_mixed.csv"


def test_more_tables_than_captions_attach_to_the_last_caption(rr, tmp_path, monkeypatch, capsys):
    pages = [FakePage("Table 4.1 : First\nTable 4.2 : Second", [good(tag="a"), good(tag="b"), good(tag="c")])]
    out, index, _ = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert [r["csv_file"] for r in index] == ["csv/Table_4.1_first.csv", "csv/Table_4.2_second.csv",
                                              "csv/Table_4.2_second_part2.csv"]
    assert [r["table_no"] for r in index] == ["4.1", "4.2", "4.2"]
    assert list(csv.reader(open(out / "csv" / "Table_4.2_second_part2.csv")))[0] == ["c00", "c01", "c02"]


def test_uncaptioned_tables_are_continuations_named_by_page(rr, tmp_path, monkeypatch, capsys):
    pages = [FakePage("", []), FakePage("no caption here", [good(), good()])]
    out, index, _ = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert [r["csv_file"] for r in index] == ["csv/p002_cont0.csv", "csv/p002_cont1.csv"]
    assert all(r["caption"] == "(continuation / no caption on page)" and r["table_no"] == "" for r in index)


def test_repeated_captions_get_numbered_suffixes(rr, tmp_path, monkeypatch, capsys):
    pages = [FakePage("Table 5.1 : Same", [good(tag="p")]), FakePage("Table 5.1 : Same", [good(tag="q")]),
             FakePage("Table 5.1 : Same", [good(tag="r")])]
    out, index, _ = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert [r["csv_file"] for r in index] == ["csv/Table_5.1_same.csv", "csv/Table_5.1_same__2.csv", "csv/Table_5.1_same__3.csv"]
    assert [list(csv.reader(open(out / r["csv_file"])))[0][0] for r in index] == ["p00", "q00", "r00"]


def test_extraction_errors_are_logged_and_skip_the_page(rr, tmp_path, monkeypatch, capsys):
    pages = [FakePage("Table 6.1 : Lost", boom=ValueError("bad page")), FakePage("Table 6.2 : Kept", [good()])]
    out, index, text = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert index[0] == {"table_no": "", "caption": "(extract error: bad page)", "page": "1", "csv_file": "",
                        "rows": "0", "cols": "0", "flag": "error"}
    assert index[1]["flag"] == "ok" and "1 tables" in text and "0 figures" in text


def test_caption_is_truncated_and_text_may_be_missing(rr, tmp_path, monkeypatch, capsys):
    long = "L" * 120
    pages = [FakePage(f"Table 7.1 : {long}", [good()]), FakePage(None, [good()])]
    out, index, _ = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert index[0]["caption"] == "L" * 90
    assert index[1]["table_no"] == "" and index[1]["csv_file"] == "csv/p002_cont0.csv"      # no text -> continuation


def test_index_is_ordered_by_page_and_counts_are_exact(rr, tmp_path, monkeypatch, capsys):
    pages = [FakePage("Table 8.1 : A", [good()]), FakePage("Table 8.2 : Fig", []),
             FakePage("", [good(), good()]), FakePage("Table 8.3 : B", [good(rows=5, cols=4)])]
    out, index, text = run(rr, tmp_path, monkeypatch, capsys, pages)
    assert [int(r["page"]) for r in index] == [1, 2, 3, 3, 4]
    assert index[-1]["rows"] == "5" and index[-1]["cols"] == "4"
    assert "4 tables" in text and "(1 figures/charts logged, no grid)" in text
    assert f"index: {out}/index.csv" in text


def test_output_directory_is_created_under_the_script_dir_for_relative_names(rr, tmp_path, monkeypatch, capsys):
    from pathlib import Path
    monkeypatch.setattr(rr, "__file__", str(tmp_path / "script" / "extract_rr.py"))
    rr.fake.pages = [FakePage("Table 9.1 : Rel", [good()])]
    monkeypatch.setattr(sys, "argv", ["extract_rr.py", "in.pdf", "sub/dir"])
    rr.main()
    assert (tmp_path / "script" / "sub" / "dir" / "csv" / "Table_9.1_rel.csv").exists()
