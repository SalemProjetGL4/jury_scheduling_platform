FROM python:3.11-slim

WORKDIR /app

COPY solver-service/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY solver-service /app/solver-service

EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--app-dir", "/app/solver-service", "--host", "0.0.0.0", "--port", "8010"]
