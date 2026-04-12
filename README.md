# Juriq

## After Cloning

1. Start the services.

```bash
docker compose up -d --build
```

1. Seed the database.

```bash
docker compose exec backend python -m app.seed --reset
```

1. Open the API docs.

- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

1. Open the frontend test console.

- Frontend UI: <http://localhost:8501>

Use it to:

- submit workflow prompts to orchestrator-service
- inspect workflow status and node history
- fetch final workflow result
- test translator-service and solver-service directly

## Bulk Student Upload (CSV/XLSX)

Backend now supports student batch import:

- Endpoint: POST /students/import
- Accepted formats: .csv, .xlsx
- Required columns in file: name, email
- Additional supported columns: promotion_year, filiere_id, filiere_name
- Optional form defaults: promotion_year, filiere_id, filiere_name, dry_run

Complex sample dataset for October 2026 is available at:

- backend/sample_data/students_october_2026_complex.csv

Example dry-run upload:

```bash
curl -X POST "http://localhost:8000/students/import" \
  -F "file=@backend/sample_data/students_october_2026_complex.csv;type=text/csv" \
  -F "dry_run=true"
```

Example real import:

```bash
curl -X POST "http://localhost:8000/students/import" \
  -F "file=@backend/sample_data/students_october_2026_complex.csv;type=text/csv" \
  -F "dry_run=false"
```

## Environment Variables

The backend and postgres services both read from [backend/.env].

Variables used:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `GROQ_API_KEY` (required for Groq provider)
- `LLM_PROVIDER` (default is `groq`)
- `LLM_MODEL` (default is `llama-3.3-70b-versatile`)
