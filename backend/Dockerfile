FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf-2.0-dev \
    libffi-dev \
    pkg-config \
    gettext \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.ubuntu.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

COPY . /app/

RUN chmod +x /app/docker-entrypoint.sh \
    && chmod +x /app/docker-celery-worker.sh /app/docker-celery-beat.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]

CMD ["gunicorn", "customers.wsgi:application", "-c", "/app/gunicorn.conf.py"]


