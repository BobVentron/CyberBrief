FROM python:3.12-slim-bookworm

WORKDIR /app

# Dépendances Python (split pour debug)
RUN pip install --no-cache-dir --prefer-binary feedparser==6.0.11 requests==2.31.0 python-dotenv==1.0.1
RUN pip install --no-cache-dir --prefer-binary beautifulsoup4==4.12.3 urllib3 pytz
RUN pip install --no-cache-dir --prefer-binary APScheduler==3.10.4
RUN pip install --no-cache-dir --prefer-binary anthropic>=0.40.0

# Code source
COPY . .

RUN mkdir -p /app/reports /app/logs

# Daemon Python long-lived — planning géré par APScheduler depuis la DB
CMD ["python", "-u", "main.py"]
