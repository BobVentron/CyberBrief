FROM python:3.12-slim-bookworm

WORKDIR /app

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

RUN mkdir -p /app/reports /app/logs

# Daemon Python long-lived — planning géré par APScheduler depuis la DB
CMD ["python", "-u", "main.py"]
