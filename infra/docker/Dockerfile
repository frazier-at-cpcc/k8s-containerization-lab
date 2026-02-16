FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir pandas pyarrow boto3

COPY src/clean_trips.py ./

ENTRYPOINT ["python", "clean_trips.py"]
