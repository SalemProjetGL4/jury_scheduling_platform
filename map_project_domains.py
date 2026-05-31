#!/usr/bin/env python3
"""
Auto-map project titles to domain IDs using keyword extraction.
Handles English and French titles with accent normalization.

Run from the repository root:
    python map_project_domains.py           # preview + confirm before writing
    python map_project_domains.py --dry-run # preview only, no writes
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata

CONTAINER = "juriq-db"
DB_USER   = "db_user"
DB_NAME   = "juriq_db"

DRY_RUN = "--dry-run" in sys.argv


def _norm(text: str) -> str:
    """Lowercase + strip diacritics so é→e, ç→c, ô→o, etc."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# ── Bucket rules ──────────────────────────────────────────────────────────────
# Applied to the FULL normalized (accent-stripped, lowercase) title.
# Dot in patterns matches any char, so "machine.learning" matches "machine learning".

_BUCKET_RULES: list[tuple[str, str]] = [
    # Computer Vision — checked before AI; no bare "detection" (too generic)
    (r"\b(computer.vision|image.recognition|object.detection|image|images|monocamera|photogramm|satellite.imagery|3d.reconstruction|segmentation|mouvement|tracking|suivi.de.balle)\b", "cv"),

    # NLP — checked before AI so NLP projects don't get buried
    (r"\b(natural.language|text.mining|information.extraction|structuration|conversationnel|chatbot|assistant.virtuel|traitement.des.appels|recommandation|recommendation|proposal.evaluation|generateur.d.application|analyse.de.cv)\b", "nlp"),

    # AI / ML — "automatisation" removed (too generic; covers DevOps/testing too)
    (r"\b(ai|ia|llm|llms|genai|gen.ai|gpt|bert|rag|ml|machine.learning|deep.learning|neural|transformer|prediction|classification|detection|intelligence.artificielle|intelligent|intelligente|generative|diffusion.model|agentic|agent.ia|agents.ia)\b", "ai"),

    # Cloud / DevOps / SRE
    (r"\b(cloud|aws|azure|gcp|kubernetes|k8s|devops|cicd|ci.cd|openshift|terraform|infrastructure|devsecops|sre|observability|monitoring|datadog|grafana|finops|github.actions)\b", "cloud"),

    # Data / Analytics — French "données", "analyse"
    (r"\b(data|etl|pipeline|analytics|streaming|warehouse|lake|big.data|bigdata|donnees|analyse|analytique|data.driven|retail.analytics|data.processing)\b", "data"),

    # Security — fixed "attacks?" to match plural; removed "fog" (was in IoT)
    (r"\b(security|secure|cyber|cybersecurity|vulnerability|vulnerabilit|attacks?|rootkit|cryptographic|encryption|offensive|intrusion|malware|forensic|securite|hardening|pentest|adversary.emulation|stealth|smart.grid)\b", "security"),

    # Web / ERP / BtoB / travel platforms
    (r"\b(web|frontend|front.end|backend|back.end|api|ui|ux|full.stack|fullstack|react|angular|vue|django|flask|fastapi|rest|graphql|btob|b2b|e.commerce|ecommerce|netsuite|license.management|licence.management|voyages?|microservice)\b", "web"),

    # Mobile
    (r"\b(mobile|android|ios|flutter|swift|kotlin)\b", "mobile"),

    # IoT / Embedded / ASIC — "fog" kept for fog computing (edge/IoT context)
    (r"\b(iot|internet.of.things|embedded|edge|fog.computing|sensor|wireless|5g|telecom|telecommunications|asic|fpga|smart.grid|vhdl|lab.device)\b", "iot"),

    # Networking
    (r"\b(network|networking|routing|firewall|vpn|protocol|packet|qos|qoe|satellite)\b", "networking"),

    # Blockchain
    (r"\b(blockchain|crypto|cryptography|ledger|nft|smart.contract|defi)\b", "blockchain"),

    # Healthcare / Biology — added "malaria", "cancer"
    (r"\b(health|healthcare|medical|clinical|genetics|bio|biology|histopathological|hospital|patient|diagnosis|malaria|disease|cancer)\b", "health"),

    # Finance — added "assurance" (French for insurance)
    (r"\b(finance|financial|bank|insurance|assurance|risk|transaction|accounting|fintech|trading|stock|supply.chain.finance)\b", "finance"),

    # Robotics
    (r"\b(robotics|robot|autonomous|drone|navigation|slam)\b", "robotics"),

    # Simulation / Game
    (r"\b(game|gaming|unity|unreal|simulation|simulating)\b", "game"),

    # Distributed Systems / Microservices (reactive systems, event-driven)
    (r"\b(microservices|distributed|reactive|reactif|event.driven|kafka|rabbitmq)\b", "distributed"),

    # Software Engineering / Management / QA — "automatisation" here for test/DevOps automation
    (r"\b(testing|qa|quality.assurance|logiciel|pilotage|outil.de.pilotage|modernisation|erp|crm|workflow|resource.planning|license|licence|netsuite|automatisation)\b", "se"),

    # XR — no standalone "ar" or "vr" to avoid French/Arabic "(FR/AR)" false positives
    (r"\b(virtual.reality|augmented.reality|mixed.reality|xr|hololens|photogrammetric.3d)\b", "xr"),

    # Quantum
    (r"\b(quantum|qubit)\b", "quantum"),
]

_BUCKET_TO_DOMAINS: dict[str, list[str]] = {
    "cv":          ["Computer Vision", "Artificial Intelligence"],
    "nlp":         ["Natural Language Processing", "Artificial Intelligence"],
    "ai":          ["Artificial Intelligence", "Machine Learning", "Deep Learning"],
    "cloud":       ["Cloud", "DevOps", "MLOps"],
    "data":        ["Data Science", "Data Engineering", "Big Data"],
    "security":    ["Security"],
    "web":         ["Web Development", "Software Engineering"],
    "mobile":      ["Mobile"],
    "iot":         ["Internet of Things", "Embedded Systems", "Edge Computing"],
    "networking":  ["Networking"],
    "blockchain":  ["Blockchain"],
    "health":      ["Healthcare", "Bioinformatics"],
    "finance":     ["Finance", "FinTech"],
    "robotics":    ["Robotics", "Autonomous Systems"],
    "game":        ["Game Development", "Simulation"],
    "distributed": ["Distributed Systems", "Software Engineering"],
    "se":          ["Software Engineering", "Web Development"],
    "xr":          ["Augmented Reality", "Virtual Reality", "Computer Graphics"],
    "quantum":     ["Quantum Computing"],
}

_STOPWORDS = {
    "a", "an", "and", "as", "at", "by", "de", "des", "du", "d", "en", "et",
    "for", "from", "in", "into", "la", "le", "les", "of", "on", "or", "pour",
    "the", "to", "un", "une", "using", "via", "with", "au", "aux", "sur",
    "based", "building", "conception", "creation", "develop", "developing",
    "development", "design", "enhanced", "improvement", "implementation",
    "improve", "integrating", "integration", "migration", "optimization",
    "optimisation", "platform", "project", "solution", "solutions",
    "system", "systems", "contribution", "participation",
}


# ── Mapping logic ─────────────────────────────────────────────────────────────

def map_title_to_domain_ids(title: str, domains: list[dict], limit: int = 3) -> list[int]:
    name_to_id: dict[str, int] = {_norm(d["name"]): int(d["id"]) for d in domains}

    results: list[int] = []

    def add(did: int) -> None:
        if did not in results:
            results.append(did)

    # Pass 1 — match bucket rules against the full normalized title
    normed = _norm(title)
    for pattern, bucket in _BUCKET_RULES:
        if not re.search(pattern, normed):
            continue
        for domain_name in _BUCKET_TO_DOMAINS.get(bucket, []):
            did = name_to_id.get(_norm(domain_name))
            if did is not None:
                add(did)
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    if len(results) >= limit:
        return results[:limit]

    # Pass 2 — exact token matching only (no substring, avoids false positives
    # like "vision" inside "approvisionnement" or "algorithm" inside "algorithme")
    tokens = {
        _norm(t).strip("_-'")
        for t in re.findall(r"[\w]+", title)
        if len(t) >= 3 and _norm(t) not in _STOPWORDS
    }
    domain_tokens: dict[int, set[str]] = {
        int(d["id"]): set(re.findall(r"[\w]+", _norm(d["name"])))
        for d in domains
    }
    for token in tokens:
        for did, toks in domain_tokens.items():
            if token in toks:          # exact token match only
                add(did)
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    return results[:limit]


# ── DB helpers ────────────────────────────────────────────────────────────────

def psql_json(query: str) -> list[dict]:
    wrapped = f"SELECT json_agg(row_to_json(t)) FROM ({query}) t"
    r = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-t", "-A", "-c", wrapped],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("DB error:", r.stderr)
        sys.exit(1)
    raw = r.stdout.strip()
    return json.loads(raw) if raw else []


def psql_exec(sql: str) -> bool:
    r = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-c", sql],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("Error:", r.stderr)
        return False
    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if psql_json("SELECT 1 AS ok") is None:
        sys.exit(1)

    projects = psql_json("SELECT id, title FROM project ORDER BY id")
    domains  = psql_json("SELECT id, name FROM domain ORDER BY id")

    if not projects:
        print("No projects found.")
        sys.exit(0)
    if not domains:
        print("No domains found — run setup_domains.py first.")
        sys.exit(0)

    print(f"Found {len(projects)} projects and {len(domains)} domains.\n")

    mapping: list[tuple[int, str, list[int], list[str]]] = []
    for p in projects:
        pid   = int(p["id"])
        title = str(p["title"] or "")
        dids  = map_title_to_domain_ids(title, domains)
        dnames = [d["name"] for d in domains if int(d["id"]) in dids]
        mapping.append((pid, title, dids, dnames))

    col = min(max(len(m[1]) for m in mapping), 90) + 2
    print(f"{'ID':<5} {'Title':<{col}} Domains")
    print("-" * (5 + col + 50))
    for pid, title, dids, dnames in mapping:
        label = ", ".join(dnames) if dnames else "(no match)"
        display = title if len(title) <= col else title[:col - 3] + "..."
        print(f"{pid:<5} {display:<{col}} {label}")

    no_match = [m for m in mapping if not m[2]]
    if no_match:
        print(f"\n  WARNING: {len(no_match)} project(s) with no domain match:")
        for pid, title, _, _ in no_match:
            print(f"    [{pid}] {title[:80]}")

    if DRY_RUN:
        print("\n[dry-run] No changes written.")
        return

    print()
    answer = input("Write these domain_ids to the database? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        print("Aborted.")
        return

    ok = errors = 0
    for pid, _, dids, _ in mapping:
        arr = "{" + ",".join(str(d) for d in dids) + "}"
        if psql_exec(f"UPDATE project SET domain_ids = '{arr}' WHERE id = {pid};"):
            ok += 1
        else:
            errors += 1

    print(f"\nDone: {ok} updated, {errors} errors.")


if __name__ == "__main__":
    main()
