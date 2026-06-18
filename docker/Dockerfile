FROM python:3.11-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get -y install --no-install-recommends curl make git && \
    rm -rf /var/lib/apt/lists/*

ARG APP_DIR=/var/app

ENV UV_CACHE_DIR=/tmp/.cache/uv \
    UV_COMPILE_BYTECODE=1 \
    UV_FROZEN=1 \
    UV_LINK_MODE=copy \
    UV_NO_MANAGED_PYTHON=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=.venv \
    VIRTUAL_ENV=.venv \
    PATH=${APP_DIR}/.venv/bin:${PATH} \
    VAULT_PATH=/vault

WORKDIR $APP_DIR

COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/

COPY Makefile pyproject.toml uv.lock README.md ./
COPY makes/ ./makes/
COPY docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh

RUN --mount=type=cache,target=${UV_CACHE_DIR} \
    uv sync --no-install-project --no-dev

COPY src/ ./src/
COPY skills/ ./skills/

RUN --mount=type=cache,target=${UV_CACHE_DIR} \
    uv sync --no-dev

ENV UV_NO_SYNC=1

ARG GIT_USER=yahelm
ARG GIT_EMAIL=vladmelekh@gmail.com

RUN git config --global safe.directory /vault && \
    git config --global user.name "${GIT_USER}" && \
    git config --global user.email "${GIT_EMAIL}" && \
    git config --global core.sshCommand "ssh -i /root/.ssh/id_ed25519 -o StrictHostKeyChecking=no"

ARG BUILD_RELEASE
ENV BUILD_RELEASE=${BUILD_RELEASE}

ENTRYPOINT ["./entrypoint.sh"]
CMD ["obsidian-mcp"]
