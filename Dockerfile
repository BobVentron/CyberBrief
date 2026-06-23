FROM python:3.12-slim-bookworm

WORKDIR /app

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY . .

# User dédié avec UID fixe 1000
RUN groupadd -g 1000 cyberbrief \
    && useradd -u 1000 -g 1000 -s /bin/false cyberbrief \
    && mkdir -p /app/reports /app/logs \
    && chown -R cyberbrief:cyberbrief /app

USER cyberbrief

# Daemon Python long-lived — planning géré par APScheduler depuis la DB
CMD ["python", "-u", "main.py"]
