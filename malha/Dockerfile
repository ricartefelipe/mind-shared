FROM python:3.12-alpine

WORKDIR /app

# Alpine recebe as correções publicadas; o pip/setuptools/wheel só servem ao build e saem da
# imagem final para não carregar vulnerabilidades de ferramenta.
RUN apk upgrade --no-cache \
  && addgroup -S app \
  && adduser -S -G app -h /app -H app \
  && mkdir -p /data \
  && chown app:app /data

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir --only-binary :all: --require-hashes -r /app/requirements.lock \
  && pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true \
  && rm -rf /usr/local/lib/python3.12/ensurepip /usr/local/lib/python3.12/site-packages/pip* /usr/local/lib/python3.12/site-packages/setuptools* /usr/local/lib/python3.12/site-packages/wheel* /usr/local/lib/python3.12/site-packages/_distutils_hack /usr/local/lib/python3.12/site-packages/pkg_resources /usr/local/bin/pip* /usr/local/bin/wheel

COPY pyproject.toml /app/pyproject.toml
COPY mind_shared /app/mind_shared
COPY corpus /app/corpus
COPY eval /app/eval

RUN chown -R app:app /app

USER app

ENV MIND_SHARED_DB=/data/mesh.sqlite
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["python", "-m", "mind_shared.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
