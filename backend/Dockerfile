FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

# Build the venv outside /app: docker-compose bind-mounts the host's
# ./backend directory onto /app at runtime, which would otherwise mask
# (and get overwritten by) the image's venv, leaving container-only
# shebangs/symlinks written back into the host tree.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
