FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY mind_shared /app/mind_shared
COPY corpus /app/corpus
COPY eval /app/eval
RUN pip install --no-cache-dir -e .

ENV MIND_SHARED_DB=/data/mesh.sqlite
EXPOSE 8000
CMD ["mind-shared", "serve", "--host", "0.0.0.0", "--port", "8000"]
