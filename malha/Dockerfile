FROM python:3.12-slim

WORKDIR /app

RUN groupadd --system app \
  && useradd --system --gid app --home /app --no-create-home app \
  && mkdir -p /data \
  && chown app:app /data

COPY requirements.txt /app/requirements.txt
COPY pyproject.toml /app/pyproject.toml
COPY mind_shared /app/mind_shared
COPY corpus /app/corpus
COPY eval /app/eval

RUN pip install --no-cache-dir --only-binary=:all: -r /app/requirements.txt \
  && pip install --no-cache-dir --no-deps -e /app \
  && chown -R app:app /app

USER app

ENV MIND_SHARED_DB=/data/mesh.sqlite
EXPOSE 8000
CMD ["mind-shared", "serve", "--host", "0.0.0.0", "--port", "8000"]
