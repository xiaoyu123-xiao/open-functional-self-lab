FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY . /workspace
RUN mkdir -p /workspace/state

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# 核心零依赖；需要 torch 时再装 requirements-train.txt
CMD ["python", "-m", "lab.cli", "doctor"]
