#!/usr/bin/env python3
"""Download the official questionnaire forms and extract their wording into text files.

Item texts, option labels and instructions are NEVER typed by hand: they are extracted
from the published forms so they stay verbatim (see CLAUDE.md, SPEC.md section 4).

Output (api/app/questionnaires/items/):
    <id>.txt                  one item per line, in order
    <id>_instructions.txt     instruction / timeframe paragraph (one line)
    dass21_options.txt        DASS-21 rating-scale labels, one per line (values 0-3)
    oasis_<n>_options.txt     OASIS item n option labels, one per line (values 0-4)
    SOURCES.json              URL, SHA-256 and retrieval date of every source

Usage (needs pdfplumber, in api/requirements-dev.txt):
    api/.venv/bin/python scripts/fetch_questionnaires.py            # download + extract
    api/.venv/bin/python scripts/fetch_questionnaires.py --check    # print line counts only

The script prints counts and similarity scores only, never the texts themselves.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "api" / "app" / "questionnaires" / "items"

SOURCES = {
    # Pfizer PHQ Screeners (free; no permission required to reproduce/translate/distribute)
    "phq9": "https://www.phqscreeners.com/images/sites/g/files/g10060481/f/201412/PHQ-9_English.pdf",
    "gad7": "https://www.phqscreeners.com/images/sites/g/files/g10060481/f/201412/GAD-7_English.pdf",
    # Official UNSW DASS site (public domain; may be copied, not modified)
    "dass21": "https://www2.psy.unsw.edu.au/DASS/Download%20files/Dass21.pdf",
    # OASIS (Norman et al., 2006): published public copy, plus a second copy for cross-checking
    "oasis": "https://depts.washington.edu/uwhatc/PDF/TF-%20CBT/pages/1%20Assessment/"
    "Standardized%20Measures/OASIS%20Overall%20Anxiety%20Scale.pdf",
    "oasis_crosscheck": "https://www.chcs.org/media/overallanxietyseverityandimpairmentscale1.pdf",
}

EXPECTED = {"gad2": 2, "gad7": 7, "phq9": 9, "oasis": 5, "dass21": 21}

TRAILING_DIGITS = re.compile(r"\s*\b0\s+1\s+2\s+3\s*$")
DIGITS_ONLY = re.compile(r"^\s*0\s+1\s+2\s+3\s*$")
ITEM_START = re.compile(r"^(\d{1,2})\.?\s+(\S.*)$")
OASIS_OPTION = re.compile(r"^([0-4])\s*=\s*(\S.*)$")


class ExtractionError(RuntimeError):
    pass


@dataclass
class Line:
    text: str
    x0: float
    top: float
    size: float
    page: int
    text_x: float  # x of the first char after a leading "N." / "N =" marker (else x0)


def clean(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"\s+", " ", s).strip()


def download(url: str, dest: Path) -> str:
    if not url.startswith("https://"):
        raise ExtractionError(f"refusing non-https URL: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 calma-fetch/1.0"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        data = r.read()
    if not data.startswith(b"%PDF"):
        raise ExtractionError(f"{url} did not return a PDF")
    dest.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read_lines(pdf_path: Path, max_x: float | None = None) -> list[Line]:
    """Text lines of a PDF; with max_x, only text left of that x (crops off answer grids)."""
    import pdfplumber

    out: list[Line] = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            if max_x is not None:
                page = page.crop((0, 0, max_x, page.height))
            for ln in page.extract_text_lines():
                chars = [c for c in ln["chars"] if c["text"].strip()]
                if not chars:
                    continue
                # Position where the text starts after a leading number marker.
                text_x = chars[0]["x0"]
                i = 0
                while i < len(chars) and re.match(r"[\d.=]", chars[i]["text"]):
                    i += 1
                if 0 < i < len(chars):
                    text_x = chars[i]["x0"]
                out.append(
                    Line(clean(ln["text"]), ln["x0"], ln["top"], chars[0]["size"], pno, text_x)
                )
    return out


def grid_x(pdf_path: Path) -> float:
    """x of the answer grid's first column ('0' on item 1's line)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for ln in page.extract_text_lines():
                text = clean(ln["text"])
                if ITEM_START.match(text) and TRAILING_DIGITS.search(text):
                    chars = [c for c in ln["chars"] if c["text"].strip()]
                    return chars[-4]["x0"]
    raise ExtractionError("answer grid not found")


def grid_instructions(pdf_path: Path) -> str:
    """Instructions of a Pfizer form, ignoring the answer-column headers to the right.

    Headers are centred over their columns, so crop at the leftmost header line
    (lines above item 1 that start right of the grid's first column, minus a margin).
    """
    import pdfplumber

    gx = grid_x(pdf_path)
    full = read_lines(pdf_path)
    first = next(i for i, ln in enumerate(full) if re.match(r"^1\.\s", ln.text))
    with pdfplumber.open(pdf_path) as pdf:
        words = pdf.pages[0].extract_words()
    # Header words sit above item 1, at or just left of the grid (they are centred on it).
    header_x = [w["x0"] for w in words if w["top"] < full[first].top - 5 and w["x0"] > gx - 60]
    cut = min(header_x + [gx]) - 2
    left = read_lines(pdf_path, max_x=cut)
    first = next(i for i, ln in enumerate(left) if re.match(r"^1\.\s", ln.text))
    return instructions_before(left, first, left[first].x0 + 10)


def instructions_before(lines: list[Line], stop: int, max_x0: float) -> str:
    """Instruction paragraph: body-size, left-aligned lines before the first item/option."""
    parts = [
        ln.text
        for ln in lines[:stop]
        if ln.size <= 12
        and ln.x0 < max_x0
        and "_" not in ln.text
        and not ln.text.startswith("(")
        and not ln.text.endswith(":")
    ]
    if not parts:
        raise ExtractionError("no instruction text found")
    return clean(" ".join(parts))


def parse_numbered(lines: list[Line], n: int, centered_digits: bool) -> tuple[list[str], int]:
    """Items numbered 1..n with a 0-1-2-3 answer grid (PHQ-9, GAD-7, DASS-21).

    Returns (items, index of item 1's line).
    centered_digits: the grid digits are vertically centred on each item's text block
    (Pfizer forms), which separates real continuation lines from labels under the table.
    """
    first = next(
        (
            i
            for i, ln in enumerate(lines)
            if (m := ITEM_START.match(ln.text))
            and m.group(1) == "1"
            and TRAILING_DIGITS.search(ln.text)
        ),
        None,
    )
    if first is None:
        raise ExtractionError("could not find item 1")

    starts: list[int] = []
    expected = 1
    for i in range(first, len(lines)):
        m = ITEM_START.match(lines[i].text)
        if m and int(m.group(1)) == expected and not DIGITS_ONLY.match(lines[i].text):
            starts.append(i)
            expected += 1
            if expected > n:
                break
    if len(starts) != n:
        raise ExtractionError(f"found {len(starts)} numbered items, expected {n}")

    items: list[str] = []
    for k, s in enumerate(starts):
        start = lines[s]
        end = starts[k + 1] if k + 1 < n else len(lines)
        block = [start]
        digit_tops = [start.top] if TRAILING_DIGITS.search(start.text) else []
        candidates: list[Line] = []
        prev_top = start.top
        for ln in lines[s + 1 : end]:
            if ln.page != start.page or "_" in ln.text or "+" in ln.text:
                break
            if DIGITS_ONLY.match(ln.text):
                digit_tops.append(ln.top)
                continue
            if abs(ln.x0 - start.text_x) > 2.5 or ln.top - prev_top > 14:
                break
            candidates.append(ln)
            prev_top = ln.top
            if TRAILING_DIGITS.search(ln.text):
                digit_tops.append(ln.top)
        if len(digit_tops) != 1:
            raise ExtractionError(f"item {k + 1}: answer grid not found exactly once")
        if centered_digits:
            # Keep the longest run of continuation lines whose block is centred on the grid.
            for take in range(len(candidates), -1, -1):
                tops = [start.top] + [c.top for c in candidates[:take]]
                if abs((min(tops) + max(tops)) / 2 - digit_tops[0]) < 2.0:
                    block += candidates[:take]
                    break
            else:
                raise ExtractionError(f"item {k + 1}: text block not aligned with answer grid")
        else:
            block += candidates
        text = " ".join(TRAILING_DIGITS.sub("", ln.text) for ln in block)
        m = ITEM_START.match(clean(text))
        if m is None:
            raise ExtractionError(f"item {k + 1}: lost its number while joining lines")
        items.append(clean(m.group(2)))
    return items, first


def parse_dass_options(lines: list[Line], before: int) -> tuple[list[str], int]:
    """The 0-3 rating-scale legend that precedes the DASS items."""
    for i in range(before - 3):
        window = lines[i : i + 4]
        if all(re.match(rf"^{v}\s+\S", ln.text) for v, ln in enumerate(window)):
            labels = [clean(re.sub(r"^\d\s+", "", ln.text)) for ln in window]
            return labels, i
    raise ExtractionError("DASS-21 rating-scale legend not found")


def parse_oasis(lines: list[Line]) -> tuple[list[str], list[list[str]], str]:
    """OASIS: 5 questions, each followed by options '0 = ...' to '4 = ...' (may wrap)."""
    items: list[list[str]] = []
    options: list[list[list[str]]] = []
    current: list[str] | None = None
    first_item = None
    for i, ln in enumerate(lines):
        t = ln.text
        if "_" in t or t.startswith("*"):
            current = None
            continue
        m_item = ITEM_START.match(t)
        m_opt = OASIS_OPTION.match(t)
        if m_item and "=" not in t[:4] and int(m_item.group(1)) == len(items) + 1:
            first_item = i if first_item is None else first_item
            items.append([m_item.group(2)])
            options.append([])
            current = items[-1]
        elif m_opt and items:
            if int(m_opt.group(1)) != len(options[-1]):
                raise ExtractionError(f"OASIS item {len(items)}: options out of order")
            options[-1].append([m_opt.group(2)])
            current = options[-1][-1]
        elif current is not None:
            current.append(t)  # wrapped continuation of the question or option
    if first_item is None:
        raise ExtractionError("OASIS: no items found")
    instructions = instructions_before(lines, first_item, lines[first_item].x0 + 2)
    item_texts = [clean(" ".join(p)) for p in items]
    option_texts = [[clean(" ".join(p)) for p in opts] for opts in options]
    for n, opts in enumerate(option_texts, 1):
        if len(opts) != 5:
            raise ExtractionError(f"OASIS item {n}: found {len(opts)} options, expected 5")
    return item_texts, option_texts, instructions


def write_lines(name: str, lines: list[str]) -> None:
    for ln in lines:
        if not ln or "\n" in ln:
            raise ExtractionError(f"{name}: empty or multi-line entry")
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def fetch() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    meta: dict[str, dict] = {}
    today = dt.date.today().isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        pdfs: dict[str, Path] = {}
        for key, url in SOURCES.items():
            path = Path(tmp) / f"{key}.pdf"
            sha = download(url, path)
            pdfs[key] = path
            meta[key] = {"url": url, "sha256": sha, "retrieved": today}
            print(f"downloaded {key}: {path.stat().st_size} bytes")

        # GAD-7 (+ GAD-2 = first two GAD-7 items, same instructions)
        lines = read_lines(pdfs["gad7"])
        gad7, first = parse_numbered(lines, 7, centered_digits=True)
        write_lines("gad7.txt", gad7)
        write_lines("gad2.txt", gad7[:2])
        write_lines("gad7_instructions.txt", [grid_instructions(pdfs["gad7"])])

        # PHQ-9
        lines = read_lines(pdfs["phq9"])
        phq9, first = parse_numbered(lines, 9, centered_digits=True)
        write_lines("phq9.txt", phq9)
        write_lines("phq9_instructions.txt", [grid_instructions(pdfs["phq9"])])

        # DASS-21
        lines = read_lines(pdfs["dass21"])
        dass, first = parse_numbered(lines, 21, centered_digits=False)
        labels, legend = parse_dass_options(lines, first)
        write_lines("dass21.txt", dass)
        write_lines("dass21_options.txt", labels)
        write_lines("dass21_instructions.txt", [instructions_before(lines, legend, 120)])

        # OASIS (+ cross-check against a second public copy)
        o_items, o_opts, o_instr = parse_oasis(read_lines(pdfs["oasis"]))
        write_lines("oasis.txt", o_items)
        for n, opts in enumerate(o_opts, 1):
            write_lines(f"oasis_{n}_options.txt", opts)
        write_lines("oasis_instructions.txt", [o_instr])
        x_items, x_opts, _ = parse_oasis(read_lines(pdfs["oasis_crosscheck"]))
        item_r = [ratio(a, b) for a, b in zip(o_items, x_items, strict=True)]
        opt_r = [
            ratio(a, b)
            for oa, ob in zip(o_opts, x_opts, strict=True)
            for a, b in zip(oa, ob, strict=True)
        ]
        print(
            f"OASIS cross-check similarity: items min={min(item_r):.3f}, "
            f"options min={min(opt_r):.3f}"
        )
        meta["oasis"]["crosscheck"] = {
            "url": SOURCES["oasis_crosscheck"],
            "item_similarity_min": round(min(item_r), 3),
            "option_similarity_min": round(min(opt_r), 3),
        }
        del meta["oasis_crosscheck"]

    meta["gad2"] = {"derived_from": "gad7", "note": "GAD-2 = GAD-7 items 1-2"}
    (OUT / "SOURCES.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")


def check() -> int:
    """Print line counts per file (never the text) and verify item counts."""
    ok = True
    for path in sorted(OUT.glob("*.txt")):
        n = len(path.read_text(encoding="utf-8").splitlines())
        want = EXPECTED.get(path.stem)
        if path.stem.startswith("oasis_") and path.stem.endswith("_options"):
            want = 5
        elif path.stem == "dass21_options":
            want = 4
        elif path.stem.endswith("_instructions"):
            want = 1
        status = "ok" if n == want else f"MISMATCH (expected {want})"
        ok &= n == want
        print(f"{path.name:28s} {n:3d} lines  {status}")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="only print line counts")
    args = ap.parse_args()
    if args.check:
        return check()
    try:
        fetch()
    except ExtractionError as e:
        print(f"extraction failed: {e}", file=sys.stderr)
        return 1
    return check()


if __name__ == "__main__":
    sys.exit(main())
