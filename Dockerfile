FROM python:3.11-slim as builder

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN groupadd -r -g 1000 airtable && useradd -r -u 1000 -g airtable airtable

WORKDIR /app

COPY src/ ./src/
COPY main.py .

RUN mkdir -p /app/inventory /app/logs && \
    chown -R airtable:airtable /app && \
    chmod -R 755 /app/inventory /app/logs

USER airtable

ENV ANSIBLE_INVENTORY_PATH=/app/inventory
ENV LOG_LEVEL=INFO
ENV POLLING_INTERVAL=2
ENV POLLING_ENABLED=true

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python main.py --test || exit 1

ENTRYPOINT ["python", "main.py"]

CMD []
