"""
PFE Planning Extractor - INSAT
Extracts student, professor, and project info from PFE planning docx files.
Usage: python3 extract_pfe.py
Outputs: pfe_data.json and pfe_data.csv
"""

import json
import csv
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

FILES = [
    (BASE_DIR / "Final_Planning_GL5_Soutenances_PFE_Septembre 2025 7 09 2025 .docx", "GL", "Septembre 2025"),
    (BASE_DIR / "Final_Planning_RT5_Soutenances_PFE_Septembre 2025  7 09 2025 bis.docx", "RT", "Septembre 2025"),
    (BASE_DIR / "Planning_GL5_Soutenances_PFE_Septembre 2024.docx", "GL", "Septembre 2024"),
    (BASE_DIR / "Planning_RT5_Soutenances_PFE_Septembre 2024.docx", "RT", "Septembre 2024"),
]

DOC_FILES = [
    (BASE_DIR / "planning soutenance - session juin 2025-GL-27 05 2025.doc", "GL", "Juin 2025"),
    (BASE_DIR / "planning soutenance - session juin2025-RT-04 06 2025.doc", "RT", "Juin 2025"),
]

def _iter_docx_blocks(doc):
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in doc.element.body:
        if child.tag.endswith("}p"):
            yield Paragraph(child, doc)
        elif child.tag.endswith("}tbl"):
            yield Table(child, doc)


def _docx_to_markdown_text(filepath):
    try:
        from docx import Document
    except Exception as exc:
        raise RuntimeError(
            "python-docx is required to parse .docx files when extract-text is not available. "
            "Install it with: pip install python-docx"
        ) from exc

    doc = Document(filepath)
    lines = []
    for block in _iter_docx_blocks(doc):
        if hasattr(block, "text") and not hasattr(block, "rows"):
            text = block.text.strip()
            if text:
                lines.append(text)
            continue

        if hasattr(block, "rows"):
            for row in block.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(cells):
                    line = "| " + " | ".join(cells) + " |"
                    lines.append(line)
    return "\n".join(lines)


def extract_text(filepath):
    try:
        result = subprocess.run(
            ["extract-text", str(filepath)],
            capture_output=True, text=True, check=True
        )
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return _docx_to_markdown_text(filepath)

def extract_text_from_ole(filepath):
    """Extract text from legacy .doc OLE files using raw string parsing."""
    import olefile
    try:
        ole = olefile.OleFileIO(filepath)
        all_data = b''
        for stream in ['WordDocument', '1Table', 'Data']:
            if ole.exists(stream):
                all_data += ole.openstream(stream).read()
        
        result = []
        current = []
        for byte in all_data:
            if 32 <= byte <= 126 or byte in (9, 10, 13):
                current.append(chr(byte))
            else:
                if len(current) >= 4:
                    result.append(''.join(current))
                current = []
        if len(current) >= 4:
            result.append(''.join(current))
        return '\n'.join(result)
    except Exception as e:
        print(f"  Warning: could not read {filepath}: {e}", file=sys.stderr)
        return ""

def parse_docx_markdown(text, department, session):
    """Parse the markdown table format from extract-text output."""
    records = []
    
    # Split into day blocks by looking for Date lines
    date_pattern = re.compile(r'Date\s*:\s*([^\|]+)', re.IGNORECASE)
    president_pattern = re.compile(r'Pr[ée]sident\s+de\s+jury\s*:?\s*([^\|\n]+)', re.IGNORECASE)
    time_pattern = re.compile(r'^\*{0,2}\s*(\d{1,2}[h:]\d{2})\s*\*{0,2}$', re.MULTILINE)
    
    lines = text.split('\n')
    
    current_date = None
    current_president = None
    current_salle = None
    current_record = {}
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Strip bold markers first for reliable metadata detection
        line_clean = re.sub(r'\*+', '', line).strip()

        # Detect date header
        date_match = date_pattern.search(line_clean)
        if date_match:
            current_date = date_match.group(1).strip().rstrip('*').strip()
        
        # Detect salle
        salle_match = re.search(r'Salle\s*:\s*([^\|]+)', line_clean, re.IGNORECASE)
        if salle_match:
            current_salle = salle_match.group(1).strip()
        
        # Detect president de jury
        pres_match = president_pattern.search(line_clean)
        if pres_match:
            current_president = pres_match.group(1).strip().rstrip('|').strip()
        
        # Detect table rows with | --- | structure - skip
        if line.startswith('| ---'):
            i += 1
            continue
        
        # Detect time slot rows
        if '|' in line:
            parts = [p.strip() for p in line.split('|')]
            parts = [p for p in parts if p]  # remove empty
            
            if not parts:
                i += 1
                continue
            
            # Check if first column is a time (strip bold markdown first)
            p0_clean = re.sub(r'\*+', '', parts[0]).strip()
            time_match = re.match(r'^(\d{1,2}[h:]\d{2})$', p0_clean)
            if time_match:
                # Save previous record if complete
                if current_record and current_record.get('student_name'):
                    records.append(current_record)
                
                current_record = {
                    'session': session,
                    'department': department,
                    'date': current_date,
                    'salle': current_salle,
                    'jury_president': current_president,
                    'time': time_match.group(1),
                    'student_name': None,
                    'project_title': None,
                    'company': None,
                    'company_supervisor': None,
                    'insat_supervisor': None,
                    'examiner': None,
                }
                
                # Sometimes candidate is on same line
                if len(parts) >= 3 and parts[1].lower() in ('candidat', 'candidate'):
                    current_record['student_name'] = clean(parts[2])
            
            elif parts and parts[0].lower() in ('candidat', 'candidate') and len(parts) >= 2:
                if current_record:
                    current_record['student_name'] = clean(parts[1]) if len(parts) > 1 else None
            
            elif parts and parts[0].lower() == 'sujet' and len(parts) >= 2:
                if current_record:
                    current_record['project_title'] = clean(parts[1])
            
            elif parts and parts[0].lower() == 'entreprise' and len(parts) >= 2:
                val = clean(parts[1])
                if val and current_record:
                    current_record['company'] = val
            
            elif parts and 'responsable entreprise' in parts[0].lower() and len(parts) >= 2:
                if current_record:
                    current_record['company_supervisor'] = clean(parts[1])
            
            elif parts and 'responsable insat' in parts[0].lower() and len(parts) >= 2:
                if current_record:
                    current_record['insat_supervisor'] = clean(parts[1])
            
            elif parts and parts[0].lower() == 'examinateur' and len(parts) >= 2:
                if current_record:
                    current_record['examiner'] = clean(parts[1])
        
        i += 1
    
    # Don't forget last record
    if current_record and current_record.get('student_name'):
        records.append(current_record)
    
    return records

def parse_ole_text(raw_text, department, session):
    """Parse the raw extracted OLE .doc text."""
    records = []
    lines = [l.strip() for l in raw_text.replace('\r', '\n').split('\n')]
    lines = [l for l in lines if l]
    
    current_date = None
    current_president = None
    current_salle = None
    current_record = {}
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Date
        date_m = re.search(r'Date\s*:\s*(.+)', line, re.IGNORECASE)
        if date_m:
            current_date = date_m.group(1).strip()
        
        # Salle
        salle_m = re.search(r'Salle\s*:\s*(\S+)', line, re.IGNORECASE)
        if salle_m:
            current_salle = salle_m.group(1).strip()
        
        # President (often split across two lines in OLE)
        if 'sident de jury' in line.lower() or 'president de jury' in line.lower():
            # look for name on same line after colon
            pres_m = re.search(r'jury\s*:?\s*(.+)', line, re.IGNORECASE)
            if pres_m and len(pres_m.group(1).strip()) > 1:
                current_president = pres_m.group(1).strip()
            elif i + 1 < len(lines):
                current_president = lines[i + 1].strip()
        
        # Time slot (e.g. 08:00 or 13:00)
        time_m = re.match(r'^(\d{1,2}:\d{2})$', line)
        if time_m:
            if current_record and current_record.get('student_name'):
                records.append(current_record)
            current_record = {
                'session': session,
                'department': department,
                'date': current_date,
                'salle': current_salle,
                'jury_president': current_president,
                'time': time_m.group(1),
                'student_name': None,
                'project_title': None,
                'company': None,
                'company_supervisor': None,
                'insat_supervisor': None,
                'examiner': None,
            }
            i += 1
            continue
        
        if not current_record:
            i += 1
            continue
        
        # The OLE extraction puts label and value alternating
        if line == 'Candidat' and i + 1 < len(lines):
            current_record['student_name'] = clean(lines[i + 1])
            i += 2
            continue
        if line == 'Sujet' and i + 1 < len(lines):
            # Sujet can span multiple lines until next keyword
            title_parts = []
            j = i + 1
            while j < len(lines) and lines[j] not in ('Entreprise', 'Responsable Entreprise', 'Responsable INSAT', 'Examinateur', 'Candidat'):
                title_parts.append(lines[j])
                j += 1
            current_record['project_title'] = clean(' '.join(title_parts))
            i = j
            continue
        if line == 'Entreprise' and i + 1 < len(lines):
            current_record['company'] = clean(lines[i + 1])
            i += 2
            continue
        if line == 'Responsable Entreprise' and i + 1 < len(lines):
            current_record['company_supervisor'] = clean(lines[i + 1])
            i += 2
            continue
        if line == 'Responsable INSAT' and i + 1 < len(lines):
            current_record['insat_supervisor'] = clean(lines[i + 1])
            i += 2
            continue
        if line == 'Examinateur' and i + 1 < len(lines):
            current_record['examiner'] = clean(lines[i + 1])
            i += 2
            continue
        
        i += 1
    
    if current_record and current_record.get('student_name'):
        records.append(current_record)
    
    return records

def clean(s):
    if not s:
        return None
    s = re.sub(r'\*+', '', s)      # remove markdown bold
    s = re.sub(r'\s+', ' ', s)     # collapse whitespace
    s = s.strip().strip('|').strip()
    return s if s else None

def main():
    all_records = []
    
    # Process .docx files
    for filepath, dept, session in FILES:
        if not Path(filepath).exists():
            print(f"Skipping missing file: {filepath}")
            continue
        print(f"Processing: {Path(filepath).name}")
        text = extract_text(filepath)
        records = parse_docx_markdown(text, dept, session)
        print(f"  → {len(records)} defenses found")
        all_records.extend(records)
    
    # Process .doc OLE files
    for filepath, dept, session in DOC_FILES:
        if not Path(filepath).exists():
            print(f"Skipping missing file: {filepath}")
            continue
        print(f"Processing: {Path(filepath).name}")
        text = extract_text_from_ole(filepath)
        records = parse_ole_text(text, dept, session)
        print(f"  → {len(records)} defenses found")
        all_records.extend(records)
    
    print(f"\nTotal records extracted: {len(all_records)}")
    
    # ── JSON output ──────────────────────────────────────────────────────────
    output_json = BASE_DIR / "pfe_data.json"
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    print(f"Saved: {output_json}")
    
    # ── CSV output ───────────────────────────────────────────────────────────
    fieldnames = [
        'session', 'department', 'date', 'time', 'salle',
        'student_name', 'project_title',
        'company', 'company_supervisor',
        'insat_supervisor', 'examiner', 'jury_president',
    ]
    output_csv = BASE_DIR / "pfe_data.csv"
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)
    print(f"Saved: {output_csv}")
    
    # ── Summary stats ────────────────────────────────────────────────────────
    print("\n── Summary ──────────────────────────────────────────")
    sessions = {}
    for r in all_records:
        key = f"{r['department']} – {r['session']}"
        sessions[key] = sessions.get(key, 0) + 1
    for k, v in sorted(sessions.items()):
        print(f"  {k}: {v} defenses")
    
    insat_profs = {}
    for r in all_records:
        if r['insat_supervisor']:
            n = r['insat_supervisor'].upper()
            insat_profs[n] = insat_profs.get(n, 0) + 1
    print(f"\n  Unique INSAT supervisors: {len(insat_profs)}")
    print(f"  Top supervisors by load:")
    for name, count in sorted(insat_profs.items(), key=lambda x: -x[1])[:10]:
        print(f"    {count}× {name}")

if __name__ == '__main__':
    main()
