FROM python:3.12-slim-bookworm

WORKDIR /app

# Dépendances système pour lxml et psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

RUN mkdir -p /app/reports /app/logs

# Daemon Python long-lived — planning géré par APScheduler depuis la DB
CMD ["python", "-u", "main.py"]
