FROM python:3.11-slim

WORKDIR /app

COPY orchestrator-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY orchestrator-service /app

EXPOSE 8011

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8011"]
