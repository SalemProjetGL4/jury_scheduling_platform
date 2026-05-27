FROM python:3.11-slim

WORKDIR /app

# Reuse solver-service requirements (includes ortools, fastapi, redis, etc.)
COPY solver-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the updater service and solver code into the image
COPY updater-service /app/updater-service
# Make the solver package available at /app/solver so imports like
# `from solver.solver_runner import ...` succeed when /app is on sys.path.
COPY solver-service/solver /app/solver

EXPOSE 8014

CMD ["uvicorn", "main:app", "--app-dir", "/app/updater-service", "--host", "0.0.0.0", "--port", "8014"]
