FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY ui ./ui
COPY README.md ./README.md

EXPOSE 8000

CMD ["sh", "-c", "python scripts/process_data.py && python -m uvicorn --app-dir /app app.main:app --host 0.0.0.0 --port 8000"]
