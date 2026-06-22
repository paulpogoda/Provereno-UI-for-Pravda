FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \\
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \\
    libffi-dev libjpeg-dev libssl-dev wget gnupg ca-certificates fonts-liberation \\
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .
RUN playwright install chromium --with-deps

COPY provereno ./provereno

ENV DATA_DIR=/app/data
VOLUME ["/app/data"]

CMD ["uvicorn", "provereno.main:app", "--host", "0.0.0.0", "--port", "8080"]
