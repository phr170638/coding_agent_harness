FROM python:3.12-slim

LABEL org.opencontainers.image.title="Coding Agent Harness"
LABEL org.opencontainers.image.description="LLM-driven autonomous coding agent with guardrails and feedback loop"

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY myagent/ myagent/

RUN pip install --no-cache-dir . && \
    pip install --no-cache-dir pytest ruff

RUN mkdir -p /workspace
WORKDIR /workspace

ENTRYPOINT ["myagent"]
CMD ["--help"]
