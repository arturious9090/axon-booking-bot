FROM python:3.13-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache
COPY . .
RUN DJANGO_SECRET_KEY=build-only DJANGO_DEBUG=true python manage.py collectstatic --noinput

FROM base AS test
RUN uv sync --frozen --no-cache
ENV PYTEST_ADDOPTS="-o cache_dir=/tmp/pytest-cache"
USER 10001:10001
CMD ["pytest"]

FROM base AS runtime
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
