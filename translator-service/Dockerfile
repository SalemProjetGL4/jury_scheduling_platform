FROM python:3.11-slim

WORKDIR /app

COPY translator-service/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY translator-service /app

EXPOSE 8012

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8012"]
