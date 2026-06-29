FROM python:3.12-slim-bookworm

WORKDIR /app

# Dépendances Python (vendorisées — aucun réseau requis au build)
COPY requirements.txt .
COPY vendor/ ./vendor/
RUN pip install --no-cache-dir --no-index --find-links vendor/ -r requirements.txt

# Code source
COPY . .

RUN mkdir -p /app/reports /app/logs

# Daemon Python long-lived — planning géré par APScheduler depuis la DB
CMD ["python", "-u", "main.py"]
