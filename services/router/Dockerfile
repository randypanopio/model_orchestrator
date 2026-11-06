FROM python:3.12.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev \
    && addgroup --system --gid 10001 router \
    && adduser --system --uid 10001 --ingroup router router

ENV PATH="/app/.venv/bin:$PATH"

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn", "router.main:app", "--host", "0.0.0.0", "--port", "8000"]
