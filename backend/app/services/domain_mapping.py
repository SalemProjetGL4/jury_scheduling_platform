from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models


def _norm(text: str) -> str:
    """Lowercase + strip diacritics (é→e, ç→c, ô→o …) for ASCII-safe matching."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_BUCKET_RULES: list[tuple[str, str]] = [
    # Computer Vision — before AI; no bare "detection" (too generic)
    (r"\b(computer.vision|image.recognition|object.detection|image|images|monocamera|photogramm|satellite.imagery|3d.reconstruction|segmentation|mouvement|tracking|suivi.de.balle)\b", "cv"),
    # NLP — before AI
    (r"\b(natural.language|text.mining|information.extraction|structuration|conversationnel|chatbot|assistant.virtuel|traitement.des.appels|recommandation|recommendation|proposal.evaluation|generateur.d.application|analyse.de.cv)\b", "nlp"),
    # AI / ML — "automatisation" removed (too generic; also matches DevOps/testing)
    (r"\b(ai|ia|llm|llms|genai|gen.ai|gpt|bert|rag|ml|machine.learning|deep.learning|neural|transformer|prediction|classification|detection|intelligence.artificielle|intelligent|intelligente|generative|diffusion.model|agentic|agent.ia|agents.ia)\b", "ai"),
    # Cloud / DevOps / SRE
    (r"\b(cloud|aws|azure|gcp|kubernetes|k8s|devops|cicd|ci.cd|openshift|terraform|infrastructure|devsecops|sre|observability|monitoring|datadog|grafana|finops|github.actions)\b", "cloud"),
    # Data / Analytics — French "données", "analyse"
    (r"\b(data|etl|pipeline|analytics|streaming|warehouse|lake|big.data|bigdata|donnees|analyse|analytique|data.driven|retail.analytics|data.processing)\b", "data"),
    # Security
    (r"\b(security|secure|cyber|cybersecurity|vulnerability|vulnerabilit|attacks?|rootkit|cryptographic|encryption|offensive|intrusion|malware|forensic|securite|hardening|pentest|adversary.emulation|stealth|smart.grid)\b", "security"),
    # Web / ERP / BtoB / travel
    (r"\b(web|frontend|front.end|backend|back.end|api|ui|ux|full.stack|fullstack|react|angular|vue|django|flask|fastapi|rest|graphql|btob|b2b|e.commerce|ecommerce|netsuite|license.management|licence.management|voyages?|microservice)\b", "web"),
    # Mobile
    (r"\b(mobile|android|ios|flutter|swift|kotlin)\b", "mobile"),
    # IoT / Embedded / ASIC
    (r"\b(iot|internet.of.things|embedded|edge|fog.computing|sensor|wireless|5g|telecom|telecommunications|asic|fpga|smart.grid|vhdl|lab.device)\b", "iot"),
    # Networking
    (r"\b(network|networking|routing|firewall|vpn|protocol|packet|qos|qoe|satellite)\b", "networking"),
    # Blockchain
    (r"\b(blockchain|crypto|cryptography|ledger|nft|smart.contract|defi)\b", "blockchain"),
    # Healthcare / Biology
    (r"\b(health|healthcare|medical|clinical|genetics|bio|biology|histopathological|hospital|patient|diagnosis|malaria|disease|cancer)\b", "health"),
    # Finance — "assurance" = French for insurance
    (r"\b(finance|financial|bank|insurance|assurance|risk|transaction|accounting|fintech|trading|stock|supply.chain.finance)\b", "finance"),
    # Robotics
    (r"\b(robotics|robot|autonomous|drone|navigation|slam)\b", "robotics"),
    # Simulation / Game
    (r"\b(game|gaming|unity|unreal|simulation|simulating)\b", "game"),
    # Distributed Systems / Microservices
    (r"\b(microservices|distributed|reactive|reactif|event.driven|kafka|rabbitmq)\b", "distributed"),
    # Software Engineering / Management / QA — "automatisation" lives here
    (r"\b(testing|qa|quality.assurance|logiciel|pilotage|outil.de.pilotage|modernisation|erp|crm|workflow|resource.planning|license|licence|netsuite|automatisation)\b", "se"),
    # XR — full phrases only to avoid "(FR/AR)" false positives
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
    "a", "an", "and", "as", "at", "au", "aux", "by", "de", "des", "du", "d",
    "en", "et", "for", "from", "in", "into", "la", "le", "les", "of", "on",
    "or", "pour", "sur", "the", "to", "un", "une", "using", "via", "with",
    "based", "building", "conception", "contribution", "creation", "develop",
    "developing", "development", "design", "enhanced", "improvement",
    "implementation", "improve", "integrating", "integration", "migration",
    "optimization", "optimisation", "participation", "platform", "project",
    "solution", "solutions", "system", "systems",
}


def _map_title(title: str, domains: list[dict[str, Any]], limit: int = 3) -> list[int]:
    name_to_id: dict[str, int] = {_norm(d["name"]): int(d["id"]) for d in domains}
    domain_tokens: dict[int, set[str]] = {
        int(d["id"]): set(re.findall(r"[\w]+", _norm(d["name"])))
        for d in domains
    }

    results: list[int] = []

    def add(did: int) -> None:
        if did not in results:
            results.append(did)

    normed = _norm(title)

    # Pass 1 — full-title bucket matching (handles multi-word phrases and French)
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

    # Pass 2 — exact token matching only (no substring to avoid false positives)
    tokens = {
        _norm(t).strip("_-'")
        for t in re.findall(r"[\w]+", title)
        if len(t) >= 3 and _norm(t) not in _STOPWORDS
    }
    for token in tokens:
        for did, toks in domain_tokens.items():
            if token in toks:
                add(did)
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break

    return results[:limit]


def infer_domain_ids(title: str, db: Session, limit: int = 3) -> list[int]:
    """Return a list of domain IDs inferred from the project title."""
    domains = db.execute(select(models.Domain)).scalars().all()
    domain_list = [{"id": d.id, "name": d.name} for d in domains]
    return _map_title(title, domain_list, limit)
