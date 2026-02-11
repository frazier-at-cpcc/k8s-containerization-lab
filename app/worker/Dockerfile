FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py .

# Run as non-root user for security
RUN useradd --create-home appuser
USER appuser

CMD ["python", "worker.py"]
