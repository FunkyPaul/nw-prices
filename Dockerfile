FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 NWP_DB=/data/prices.db
WORKDIR /srv/nwprices

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY manage.py .

RUN useradd --system --uid 1000 nwp && mkdir -p /data && chown nwp /data
USER nwp
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
# 1 Worker + Threads: SQLite mag keine vielen parallelen Schreiber; Timeout grosszuegig fuer grosse Uploads
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "300", "app.web:app"]
