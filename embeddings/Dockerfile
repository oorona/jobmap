FROM python:3.13-slim
WORKDIR /app
COPY embeddings/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app/embedding_models.py ./embedding_models.py
COPY embeddings/server.py .
ENV HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false HF_HOME=/models/huggingface HF_XET_CACHE=/models/xet XDG_CACHE_HOME=/models/cache
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010", "--no-access-log"]
