FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /probity

COPY pyproject.toml README.md Makefile EVAL_SPEC.md PROJECT_STATE.md INTERFACE_CONTRACT.md ./
COPY gauntlet ./gauntlet
COPY demo ./demo
COPY tasks ./tasks
COPY tests ./tests
COPY docs ./docs
COPY scripts ./scripts

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[dev]"

ENTRYPOINT ["python", "scripts/probity_docker_entry.py"]
CMD ["help"]
