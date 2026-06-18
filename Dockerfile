# Multi-stage Dockerfile for containerized ZER0CODE
# Pre-installs common pentesting tools for security workflows
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl wget nmap dnsutils whois netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["zer0code"]
