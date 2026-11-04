# 可选路径。v0.1 不需要 Docker 也能完整跑通（纯标准库）。
# 构建：docker build -f sandbox/Dockerfile -t ofsl/lab:0.1.0 .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 非 root 运行（与 docker-compose.yml 的 user 对应）。
RUN groupadd -g 1000 lab && useradd -m -u 1000 -g 1000 lab

WORKDIR /workspace

# 核心零依赖，因此这里不装任何第三方包；需要时再单独 COPY 可选清单。
COPY --chown=lab:lab . /workspace
RUN mkdir -p /workspace/state && chown -R lab:lab /workspace/state

USER lab

HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD ["python", "-m", "lab.cli", "status"]

CMD ["python", "-m", "lab.cli", "doctor"]
