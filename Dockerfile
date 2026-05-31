FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY pipeline ./pipeline
COPY scripts ./scripts
COPY data ./data
COPY dashboard ./dashboard
COPY docs ./docs
COPY tests ./tests
COPY pytest.ini .

ENV PYTHONPATH=/app
ENV DATA_DIR=/app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
