FROM python:3.13-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image
ADD . /app

ENV UV_LINK_MODE=copy

# Sync the project into a new environment, using the frozen lockfile
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --compile-bytecode

CMD ["uv", "run", "src/main.py"]