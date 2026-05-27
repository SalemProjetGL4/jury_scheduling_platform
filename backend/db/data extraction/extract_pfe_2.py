"""
extract_pfe_2.py
================
Extracts PFE jury planning data from INSAT planning Word documents (.docx).

Document structure (per table):
  Row 0 : [Salle : X  |  Session : Y  |  Date : Z]
  Row 1 : [Président de jury : Name  |  ...  |  ...]
  Row 2+: [time  |  label  |  value]   (one row per field per candidate)

Auto-discovers all .docx files in the same folder as this script (or in a
data/ subfolder if one exists).  Filière code is derived from the filename
(e.g. Final_Planning_GL5_...docx → "GL").

Outputs
-------
  pfe_extracted.csv  – one row per defence, written next to the source files
  (JSON output is optional; enable by passing --json)

Usage
-----
    python extract_pfe_2.py                   # auto-discover *.docx here
    python extract_pfe_2.py path/to/file.docx [...]
    python extract_pfe_2.py --json            # also write pfe_extracted.json
"""

import re
import csv
import json
import argparse
import sys
from pathlib import Path

try:
    from docx import Document
except ImportError:
    print("ERROR: python-docx is required.  Run: pip install python-docx", file=sys.stderr)
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR   = SCRIPT_DIR / "data" if (SCRIPT_DIR / "data").is_dir() else SCRIPT_DIR

COLUMNS = [
    "date", "time", "salle", "session", "filiere", "jury_president",
    "student_name", "project_title",
    "company", "company_supervisor",
    "insat_supervisor", "examiner",
]

# 2-3 uppercase letters immediately before a digit: GL5, RT5 → GL, RT
FILIERE_NAME_RE = re.compile(r"(?<![A-Z])([A-Z]{2,3})(?=\d)")
TIME_RE         = re.compile(r"(\d{1,2})[h:](\d{2})")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def normalize(s: str | None) -> str | None:
    if not s:
        return None
    s = re.sub(r"\*+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def filiere_from_filename(path: Path) -> str:
    m = FILIERE_NAME_RE.search(path.stem)
    if m:
        return m.group(1)
    m2 = re.search(r"\b([A-Z]{2,3})\b", path.stem)
    return m2.group(1) if m2 else ""


def _norm_time(raw: str) -> str | None:
    m = TIME_RE.search(raw)
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else (raw.strip() or None)


# ──────────────────────────────────────────────────────────────────────────────
# Table parser
# ──────────────────────────────────────────────────────────────────────────────

def _parse_table(table, filiere: str) -> list[dict]:
    rows = table.rows
    if len(rows) < 3:
        return []

    # Row 0: Salle / Session / Date
    header = [c.text.strip() for c in rows[0].cells]
    salle = session = date = ""
    for cell in header:
        m = re.search(r"Salle\s*:\s*(.+)", cell, re.IGNORECASE)
        if m:
            salle = m.group(1).strip()
        m = re.search(r"Session\s*:\s*(.+)", cell, re.IGNORECASE)
        if m:
            session = m.group(1).strip()
        m = re.search(r"Date\s*:\s*(.+)", cell, re.IGNORECASE)
        if m:
            date = m.group(1).strip()

    if not date:
        return []

    # Row 1: Président de jury
    jury_president = ""
    for cell in (c.text.strip() for c in rows[1].cells):
        m = re.search(r"Pr[ée]sident\s+de\s+jury\s*:?\s*(.+)", cell, re.IGNORECASE)
        if m:
            jury_president = m.group(1).strip()
            break

    # Rows 2+: [time, label, value]
    records: list[dict] = []
    current: dict | None = None
    current_time: str | None = None

    def _flush():
        if current and current.get("student_name"):
            records.append(dict(current))

    for row in rows[2:]:
        cells = [c.text.strip().replace("\n", " ") for c in row.cells]
        if len(cells) < 3:
            continue
        raw_time, label, value = cells[0], cells[1].strip(), cells[2].strip()
        label_lc = label.lower()

        if raw_time:
            t = _norm_time(raw_time)
            if t:
                current_time = t

        if label_lc in ("candidat", "candidate"):
            _flush()
            current = {
                "date":          normalize(date),
                "time":          current_time,
                "salle":         normalize(salle),
                "session":       normalize(session),
                "filiere":       filiere,
                "jury_president": normalize(jury_president),
                "student_name":  normalize(value),
                "project_title": None,
                "company":       None,
                "company_supervisor": None,
                "insat_supervisor":   None,
                "examiner":      None,
            }
        elif current:
            if label_lc == "sujet":
                existing = current["project_title"]
                current["project_title"] = normalize(
                    (existing + " " + value) if existing else value
                )
            elif label_lc == "entreprise":
                current["company"] = normalize(value)
            elif "responsable entreprise" in label_lc:
                current["company_supervisor"] = normalize(value)
            elif "responsable insat" in label_lc:
                current["insat_supervisor"] = normalize(value)
            elif label_lc == "examinateur":
                current["examiner"] = normalize(value)

    _flush()
    return records


def parse_docx(docx_path: str) -> list[dict]:
    path    = Path(docx_path)
    filiere = filiere_from_filename(path)
    doc     = Document(docx_path)
    records: list[dict] = []
    for table in doc.tables:
        records.extend(_parse_table(table, filiere))
    return records


# ──────────────────────────────────────────────────────────────────────────────
# Post-processing
# ──────────────────────────────────────────────────────────────────────────────

COMPANY_RE = re.compile(
    r"\b(GmbH|LLC|Ltd|Inc|SAS|SA|AG|AB|BV|NV|Consulting|Solutions|"
    r"Technologies|Labs?|Services|Group|Paribas|Company|Semiconductors|"
    r"Training|Studio|Platform|University|Institut|Amazon|Google|EY|"
    r"Ernst|Qantev|Metaplanet|Everbloo|Masteur|Macadam|Zortify|"
    r"NextMatters|Vectors|thunderCode|Thunder)\b",
    re.IGNORECASE,
)
PERSON_RE = re.compile(r"^[A-ZÀÂÄÉÈÊËÎÏÔÙÛÜ][a-zàâäéèêëîïôùûü]")

NAME_MAP: dict[str, str] = {
    "dorsaf sbei":                  "Dorsaf Sebai",
    "dorsaf sebai":                 "Dorsaf Sebai",
    "aymen sellouati":              "Aymen Sellaouti",
    "olfa mosbahi":                 "Olfa Mosbehi",
    "ilhem abdelhedi":              "Ilhem Abdelhedi Abdelmoulah",
    "ilhem abdelhedi abdelmoulah":  "Ilhem Abdelhedi Abdelmoulah",
    "narjess robbana":              "Narjess Robbana",
    "riadh robbana":                "Riadh Robbana",
    "wided miled-souid":            "Wided Miled-Souid",
    "wided miled souid":            "Wided Miled-Souid",
    "wided souid-miled":            "Wided Miled-Souid",
    "imen mami":                    "Imen Mami",
    "rabaa youssef":                "Rabaa Youssef",
    "saloua ben yahia":             "Saloua Ben Yahia",
    "amira jouirou":                "Amira Jouirou",
    "ghada gasmi":                  "Ghada Gasmi",
    "hazar mliki":                  "Hazar Mliki",
    "hajer taktak":                 "Hajer Taktak",
    "sana hamdi":                   "Sana Hamdi",
    "sonia bouzidi":                "Sonia Bouzidi",
    "lilia sfaxi":                  "Lilia Sfaxi",
    "asma ben hassouna":            "Asma Ben Hassouna",
}


def fix_entreprise_swap(records: list[dict]) -> list[dict]:
    for r in records:
        ent  = r.get("company") or ""
        resp = r.get("company_supervisor") or ""
        if (ent and resp
                and not COMPANY_RE.search(ent)
                and COMPANY_RE.search(resp)
                and PERSON_RE.match(ent)):
            r["company"], r["company_supervisor"] = resp, ent
    return records


def fix_names(records: list[dict]) -> list[dict]:
    for r in records:
        for field in ("jury_president", "insat_supervisor", "examiner"):
            v = r.get(field) or ""
            canonical = NAME_MAP.get(v.lower())
            if canonical:
                r[field] = canonical
    return records


def fix_slot_times(records: list[dict]) -> list[dict]:
    def same_block(a: dict, b: dict) -> bool:
        return a["date"] == b["date"] and a["jury_president"] == b["jury_president"]

    for i in range(1, len(records)):
        if not records[i]["time"] and same_block(records[i], records[i - 1]):
            records[i]["time"] = records[i - 1]["time"]
    for i in range(len(records) - 2, -1, -1):
        if not records[i]["time"] and same_block(records[i], records[i + 1]):
            records[i]["time"] = records[i + 1]["time"]
    return records


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Extract PFE jury data from .docx planning files."
    )
    ap.add_argument(
        "docx_files", nargs="*",
        help="Explicit .docx paths. Omit to auto-discover in the data/ folder.",
    )
    ap.add_argument(
        "-o", "--output",
        default=str(DATA_DIR / "pfe_extracted.csv"),
        help="Output CSV path (default: <data_dir>/pfe_extracted.csv)",
    )
    ap.add_argument("--json", action="store_true", help="Also write a JSON file.")
    args = ap.parse_args()

    if args.docx_files:
        paths = [Path(p) for p in args.docx_files]
    else:
        paths = sorted(DATA_DIR.glob("*.docx"))
        if not paths:
            print(f"No .docx files found in {DATA_DIR}", file=sys.stderr)
            sys.exit(1)

    all_records: list[dict] = []
    for path in paths:
        filiere = filiere_from_filename(path)
        print(f"  Parsing {path.name}  (filière={filiere or '?'}) ...", file=sys.stderr)
        recs = parse_docx(str(path))
        recs = fix_entreprise_swap(recs)
        recs = fix_names(recs)
        recs = fix_slot_times(recs)
        print(f"    → {len(recs)} defences", file=sys.stderr)
        all_records.extend(recs)

    out_csv = Path(args.output)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_records)
    print(f"\n✓ CSV → {out_csv}  ({len(all_records)} records)", file=sys.stderr)

    if args.json:
        out_json = out_csv.with_suffix(".json")
        with out_json.open("w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=2)
        print(f"✓ JSON → {out_json}", file=sys.stderr)

    # Summary
    print("\n── by filière ──────────────────────────────────────", file=sys.stderr)
    counts: dict[str, int] = {}
    for r in all_records:
        k = r.get("filiere") or "?"
        counts[k] = counts.get(k, 0) + 1
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v} defences", file=sys.stderr)

    supervisors = {}
    for r in all_records:
        s = r.get("insat_supervisor")
        if s:
            supervisors[s.upper()] = supervisors.get(s.upper(), 0) + 1
    print(f"\n  Unique INSAT supervisors: {len(supervisors)}", file=sys.stderr)
    for name, cnt in sorted(supervisors.items(), key=lambda x: -x[1])[:10]:
        print(f"    {cnt}× {name}", file=sys.stderr)


if __name__ == "__main__":
    main()
