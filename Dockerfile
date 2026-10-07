# London Tube Assistant: one image runs the Streamlit app.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/models

WORKDIR /app

# curl is only used by the health check
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model into the image, so containers start without downloading it
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/models')"

COPY . .

# Run as a normal user, not root
RUN useradd --create-home --uid 1000 tube \
    && mkdir -p /app/data/chroma /app/data/raw \
    && chown -R tube:tube /app /models
USER tube

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

# Build the knowledge base if it isn't there yet (kept in a volume), then serve.
# If TfL can't be reached the app still starts; live tools keep working.
CMD ["sh", "-c", "python -m tube.bootstrap || echo 'Bootstrap failed: guidance search disabled'; exec python -m streamlit run app/streamlit_app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true"]
