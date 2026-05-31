#!/usr/bin/env python3
"""
seed_pfe_csv.py
===============
Seeds department, filière, domain, professor, student, and project tables
from the CSV produced by extract_pfe_2.py.

No sessions, slots, or assignments are created.

Pre-condition: run truncate.sql first if you need a clean slate:
  docker cp backend/db/truncate.sql juriq-db:/tmp/truncate.sql
  docker exec juriq-db psql -U db_user -d juriq_db -f /tmp/truncate.sql

Usage
-----
  python seed_pfe_csv.py
  python seed_pfe_csv.py --csv pfe_extracted.csv
  python seed_pfe_csv.py --host localhost --port 5432 --dbname juriq_db \\
                          --user db_user --password abc123
"""

import csv
import re
import unicodedata
import argparse
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2-binary required.  Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Paths & static config
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).resolve().parent
DEFAULT_CSV = SCRIPT_DIR / "pfe_extracted.csv"
BACKEND_ENV = SCRIPT_DIR.parent.parent / ".env"   # backend/.env

# One department, one filière, and one domain per filière code.
_DEPT_NAME    = {"GL": "GL",   "RT": "RT"}
_FILIERE_NAME = {"GL": "GL5",  "RT": "RT5"}
_DOMAIN_NAME  = {"GL": "Génie Logiciel", "RT": "Réseaux et Télécommunications"}

MAX_JURIES         = 15
PROF_EMAIL_DOMAIN  = "insat.ucar.tn"
STU_EMAIL_DOMAIN   = "insat.tn"


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _load_env(path: Path) -> dict:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", ".", _strip_accents(name).lower()).strip(".")


def _unique_email(name: str, email_domain: str, used: set) -> str:
    base = _slug(name)
    candidate = f"{base}@{email_domain}"
    n = 2
    while candidate in used:
        candidate = f"{base}.{n}@{email_domain}"
        n += 1
    used.add(candidate)
    return candidate


def _title_name(s: str) -> str:
    """Title-case a name while preserving hyphens."""
    out = []
    for part in s.strip().split():
        if "-" in part:
            out.append("-".join(w.capitalize() for w in part.split("-")))
        else:
            out.append(part.capitalize())
    return " ".join(out)


def _canonical_prof(raw: str | None) -> str | None:
    if not raw:
        return None
    name = raw.strip()
    return _title_name(name) if name else None


def _promotion_date(session_label: str | None) -> str:
    """Best-effort ISO date from 'Septembre 2025' → '2025-09-01'."""
    if session_label:
        m = re.search(r"\b(20\d{2})\b", session_label)
        if m:
            return f"{m.group(1)}-09-01"
    return "2025-09-01"


# ─────────────────────────────────────────────────────────────────────────────
# DB helpers  (SELECT-then-INSERT for tables without unique name constraint)
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create(cur, table: str, name_col: str, name: str,
                   extra_cols: dict | None = None) -> int:
    """Return existing id or INSERT and return new id."""
    where = f"{name_col} = %s"
    params: list = [name]
    if extra_cols:
        for col, val in extra_cols.items():
            where += f" AND {col} = %s"
            params.append(val)
    cur.execute(f"SELECT id FROM {table} WHERE {where}", params)
    row = cur.fetchone()
    if row:
        return row[0]
    cols = [name_col] + (list(extra_cols.keys()) if extra_cols else [])
    vals = [name]    + (list(extra_cols.values()) if extra_cols else [])
    placeholders = ", ".join(["%s"] * len(cols))
    cur.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) RETURNING id",
        vals,
    )
    return cur.fetchone()[0]


# ─────────────────────────────────────────────────────────────────────────────
# Main seeder
# ─────────────────────────────────────────────────────────────────────────────

def seed(conn, csv_path: Path) -> None:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    filieres_in_csv = {r.get("filiere", "").strip().upper() for r in rows}
    known_codes = {c for c in filieres_in_csv if c in _DEPT_NAME}
    print(f"  {len(rows)} records | filieres: {sorted(known_codes)}", file=sys.stderr)

    with conn.cursor() as cur:

        # ── 1. Departments ────────────────────────────────────────────────────
        dept_ids: dict[str, int] = {}
        for code in sorted(known_codes):
            dept_ids[code] = _get_or_create(cur, "department", "name", _DEPT_NAME[code])
        print(f"  Departments: {dept_ids}", file=sys.stderr)

        # ── 2. Filieres ───────────────────────────────────────────────────────
        filiere_ids: dict[str, int] = {}
        for code in sorted(known_codes):
            filiere_ids[code] = _get_or_create(
                cur, "filiere", "name", _FILIERE_NAME[code],
                extra_cols={"department_id": dept_ids[code]},
            )
        print(f"  Filieres: {filiere_ids}", file=sys.stderr)

        # ── 3. Domains ────────────────────────────────────────────────────────
        domain_ids: dict[str, int] = {}
        for code in sorted(known_codes):
            domain_ids[code] = _get_or_create(cur, "domain", "name", _DOMAIN_NAME[code])
        print(f"  Domains: {domain_ids}", file=sys.stderr)

        # ── 4. Department ↔ Domain links ──────────────────────────────────────
        for code in known_codes:
            cur.execute(
                "INSERT INTO department_domain (department_id, domain_id)"
                " VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (dept_ids[code], domain_ids[code]),
            )

        # ── 5. Collect professors (all three roles) ───────────────────────────
        # Track: key (lowercase) → (canonical_name, primary_filiere_code)
        # Primary = first role encountered in order: supervisor > president > examiner.
        prof_info: dict[str, tuple[str, str]] = {}

        role_fields = ("insat_supervisor", "jury_president", "examiner")
        for r in rows:
            code = r.get("filiere", "").strip().upper()
            if code not in known_codes:
                continue
            for field in role_fields:
                name = _canonical_prof(r.get(field))
                if not name:
                    continue
                key = name.lower()
                if key not in prof_info:
                    prof_info[key] = (name, code)

        # ── 6. Insert professors ──────────────────────────────────────────────
        prof_emails: set[str] = set()
        professor_ids: dict[str, int] = {}

        for key, (name, code) in sorted(prof_info.items()):
            email = _unique_email(name, PROF_EMAIL_DOMAIN, prof_emails)
            cur.execute(
                "INSERT INTO professor (name, email, department_id, max_juries)"
                " VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (email) DO NOTHING RETURNING id",
                (name, email, dept_ids[code], MAX_JURIES),
            )
            row = cur.fetchone()
            if row:
                professor_ids[key] = row[0]
            else:
                cur.execute("SELECT id FROM professor WHERE email = %s", (email,))
                professor_ids[key] = cur.fetchone()[0]

        print(f"  Professors: {len(professor_ids)}", file=sys.stderr)

        # ── 7. Professor ↔ Domain links ───────────────────────────────────────
        for key, (_, code) in prof_info.items():
            prof_id = professor_ids.get(key)
            if prof_id is None:
                continue
            cur.execute(
                "INSERT INTO professor_domain (professor_id, domain_id)"
                " VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (prof_id, domain_ids[code]),
            )

        # ── 8. Students ───────────────────────────────────────────────────────
        stu_emails: set[str] = set()
        student_ids: dict[str, int] = {}
        skipped_students = 0

        for r in rows:
            code = r.get("filiere", "").strip().upper()
            if code not in filiere_ids:
                continue
            raw_name = (r.get("student_name") or "").strip()
            if not raw_name:
                continue
            name = _title_name(raw_name)
            key  = name.lower()
            if key in student_ids:
                continue

            email     = _unique_email(name, STU_EMAIL_DOMAIN, stu_emails)
            promotion = _promotion_date(r.get("session"))

            cur.execute(
                "INSERT INTO student (name, email, promotion, filiere_id)"
                " VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (email) DO NOTHING RETURNING id",
                (name, email, promotion, filiere_ids[code]),
            )
            row = cur.fetchone()
            if row:
                student_ids[key] = row[0]
            else:
                cur.execute("SELECT id FROM student WHERE email = %s", (email,))
                student_ids[key] = cur.fetchone()[0]

        print(f"  Students: {len(student_ids)}", file=sys.stderr)

        # ── 9. Projects ───────────────────────────────────────────────────────
        inserted_projects = 0
        skipped_projects  = 0

        for r in rows:
            code = r.get("filiere", "").strip().upper()
            if code not in domain_ids:
                continue

            title = (r.get("project_title") or "").strip()
            if not title:
                skipped_projects += 1
                continue

            sup_name = _canonical_prof(r.get("insat_supervisor"))
            stu_name = _title_name((r.get("student_name") or "").strip())

            sup_id = professor_ids.get(sup_name.lower()) if sup_name else None
            stu_id = student_ids.get(stu_name.lower())

            if sup_id is None or stu_id is None:
                print(
                    f"  SKIP '{title[:50]}': "
                    f"{'no supervisor' if sup_id is None else 'no student'}",
                    file=sys.stderr,
                )
                skipped_projects += 1
                continue

            # Avoid duplicate projects for the same student.
            cur.execute(
                "SELECT id FROM project WHERE student_id = %s AND title = %s",
                (stu_id, title),
            )
            if cur.fetchone():
                continue

            cur.execute(
                "INSERT INTO project (title, domain_ids, supervisor_id, student_id)"
                " VALUES (%s, %s, %s, %s)",
                (title, [domain_ids[code]], sup_id, stu_id),
            )
            inserted_projects += 1

        print(
            f"  Projects: {inserted_projects} inserted"
            + (f", {skipped_projects} skipped" if skipped_projects else ""),
            file=sys.stderr,
        )

    conn.commit()
    print("\n✓ Seed complete.", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    env = _load_env(BACKEND_ENV)

    ap = argparse.ArgumentParser(description="Seed PFE CSV data into juriq_db.")
    ap.add_argument("--csv",      default=str(DEFAULT_CSV), help="Path to pfe_extracted.csv")
    ap.add_argument("--host",     default="localhost",       help="DB host (default: localhost)")
    ap.add_argument("--port",     default=int(env.get("POSTGRES_PORT", "5432")), type=int)
    ap.add_argument("--dbname",   default=env.get("POSTGRES_DB",       "juriq_db"))
    ap.add_argument("--user",     default=env.get("POSTGRES_USER",     "db_user"))
    ap.add_argument("--password", default=env.get("POSTGRES_PASSWORD", ""))
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting → {args.user}@{args.host}:{args.port}/{args.dbname}", file=sys.stderr)
    try:
        conn = psycopg2.connect(
            host=args.host, port=args.port,
            dbname=args.dbname, user=args.user, password=args.password,
        )
    except psycopg2.OperationalError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        print("Make sure Docker is running and the DB container is up.", file=sys.stderr)
        sys.exit(1)

    try:
        seed(conn, csv_path)
    except Exception as e:
        conn.rollback()
        print(f"ERROR during seed: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
