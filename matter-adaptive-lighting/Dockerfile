ARG BUILD_FROM
FROM $BUILD_FROM

# uv (version-pinned) for a reproducible install straight from uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

RUN apk add --no-cache python3

ENV UV_PYTHON=/usr/bin/python3 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /opt/app
COPY pyproject.toml uv.lock ./
COPY src ./src
# --frozen: fail rather than re-resolve if the lock is stale; --no-dev: runtime deps only.
RUN uv sync --frozen --no-dev --no-editable

# Unbuffered so logs reach `ha apps logs` promptly (the console script has no -u).
ENV PYTHONUNBUFFERED=1
CMD ["/opt/venv/bin/matter-adaptive-lighting", "run"]
