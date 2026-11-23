import importlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class FakePage:
    def __init__(self, text="", tables=(), boom=None):
        self.text, self._tables, self.boom = text, list(tables), boom
        self.seen_settings = None

    def extract_text(self):
        return self.text

    def extract_tables(self, settings=None):
        self.seen_settings = settings
        if self.boom:
            raise self.boom
        return self._tables


class FakePDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def rr(monkeypatch):
    """extract_rr imported against a fake pdfplumber, so the suite needs neither the library nor a PDF."""
    fake = types.ModuleType("pdfplumber")
    fake.opened = []
    fake.pages = []

    def open_(path):
        fake.opened.append(path)
        return FakePDF(fake.pages)

    fake.open = open_
    monkeypatch.setitem(sys.modules, "pdfplumber", fake)
    sys.modules.pop("extract_rr", None)
    mod = importlib.import_module("extract_rr")
    mod.fake = fake
    yield mod
    sys.modules.pop("extract_rr", None)
