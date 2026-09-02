# First Cairn Digital
# P26003 customer live shell and container runtime

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system fcd && adduser --system --ingroup fcd --home /app fcd

COPY requirements.txt constraints.txt pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --constraint constraints.txt --requirement requirements.txt .

RUN mkdir -p /app/data/artifacts /app/data/bundles /app/data/quarantine \
    && chown -R fcd:fcd /app

USER fcd

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).getcode() == 200 else 1)"

CMD ["uvicorn", "unpaid_invoice_escalator.live_app:app", "--host", "0.0.0.0", "--port", "8000"]
