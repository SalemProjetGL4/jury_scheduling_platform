# Juriq

## After Cloning

1. Start the services.

```bash
docker compose up -d --build
```

2. Seed the database.

```bash
docker compose exec backend python -m app.seed --reset
```

3. Open the API docs.

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Environment Variables

The backend and postgres services both read from [backend/.env].

Variables used:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`

