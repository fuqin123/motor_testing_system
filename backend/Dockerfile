FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

ARG PIP_INDEX_URL=https://pypi.org/simple

COPY requirements.txt ./
RUN pip install --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY healthcheck.py ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "healthcheck.py"]

ENTRYPOINT ["docker-entrypoint.sh"]
