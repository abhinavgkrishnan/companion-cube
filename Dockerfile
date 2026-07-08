# Backend image: FastAPI + embedded Qdrant + ONNX models, one container.
# Models are pre-downloaded at build time so cold starts don't pull ~300MB.
# The vector store + beat taxonomies are baked in from data/ (see .dockerignore
# for what's excluded — raw/clean wiki text and tag caches never ship).

FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/models

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# bge-small (dense), bm25 (sparse), ms-marco L-12 (reranker)
RUN python -c "from fastembed import TextEmbedding, SparseTextEmbedding; \
    from fastembed.rerank.cross_encoder import TextCrossEncoder; \
    TextEmbedding('BAAI/bge-small-en-v1.5'); \
    SparseTextEmbedding('Qdrant/bm25'); \
    TextCrossEncoder('Xenova/ms-marco-MiniLM-L-12-v2')"

COPY companion_cube/ companion_cube/
COPY api/ api/
COPY data/ data/

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
