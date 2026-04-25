FROM python:3.11-slim

WORKDIR /app

COPY frontend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY frontend /app

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true"]
