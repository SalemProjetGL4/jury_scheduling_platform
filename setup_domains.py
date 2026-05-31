#!/usr/bin/env python3
"""
Populate the domain table in the running Docker Postgres container.
Run from the repository root:
    python setup_domains.py
Requires the juriq-db container to be running.
"""
import subprocess
import sys

CONTAINER = "juriq-db"
DB_USER   = "db_user"
DB_NAME   = "juriq_db"

CANONICAL_DOMAINS = [
    "Artificial Intelligence",
    "Machine Learning",
    "Data Science",
    "Data Engineering",
    "Internet of Things",
    "Security",
    "Cloud",
    "DevOps",
    "Web Development",
    "Mobile",
    "Blockchain",
    "Networking",
    "Embedded Systems",
    "Natural Language Processing",
    "Computer Vision",
    "Databases",
    "Human-Computer Interaction",
    "Bioinformatics",
    "Finance",
    "Healthcare",
    "Robotics",
    "Distributed Systems",
    "Software Engineering",
    "Deep Learning",
    "Big Data",
    "MLOps",
    "Edge Computing",
    "Quantum Computing",
    "Computer Graphics",
    "Augmented Reality",
    "Virtual Reality",
    "Game Development",
    "Information Retrieval",
    "Operating Systems",
    "Compilers",
    "Formal Methods",
    "Algorithm Design",
    "Digital Twins",
    "Simulation",
    "Autonomous Systems",
    "FinTech",
]


def psql(sql: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME, "-c", sql],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def main():
    # Check container is reachable
    rc, out, err = psql("SELECT 1;")
    if rc != 0:
        print(f"Cannot reach container '{CONTAINER}':")
        print(err or out)
        print("\nMake sure the stack is running:  docker compose up -d")
        sys.exit(1)

    print(f"Connected to {CONTAINER}/{DB_NAME}")
    answer = input(
        "This will TRUNCATE the domain table, clear all project domain links, and re-insert all domains. Continue? [y/N]: "
    ).strip().lower()
    if answer not in ("y", "yes"):
        print("Aborted.")
        sys.exit(0)

    # Clear domain_ids on all projects first (no FK to worry about, just stale data)
    rc, out, err = psql("UPDATE project SET domain_ids = '{}';")
    if rc != 0:
        print("Failed to clear project domain_ids:", err)
        sys.exit(1)
    print("Cleared domain_ids on all projects.")

    # Truncate — CASCADE clears professor_domain rows too
    rc, out, err = psql("TRUNCATE TABLE domain RESTART IDENTITY CASCADE;")
    if rc != 0:
        print("TRUNCATE failed:", err)
        sys.exit(1)
    print("Truncated domain table.")

    # Insert all domains in one statement
    values = ", ".join(f"('{name.replace(chr(39), chr(39)*2)}')" for name in CANONICAL_DOMAINS)
    rc, out, err = psql(f"INSERT INTO domain (name) VALUES {values};")
    if rc != 0:
        print("INSERT failed:", err)
        sys.exit(1)

    print(f"Inserted {len(CANONICAL_DOMAINS)} domains.")

    # Show result
    rc, out, err = psql("SELECT id, name FROM domain ORDER BY id;")
    print("\n" + out)
    print("\nDone.")


if __name__ == "__main__":
    main()
