# IRIS runs as one process with several threads on purpose. A check spends about eighty-five
# per cent of its time waiting on OpenAI, Brave and publishers, so threads buy the concurrency
# that extra processes would not -- and the two models cost a gigabyte of memory that every
# extra worker process would duplicate, along with its article cache and its per-publisher
# request limit.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    IRIS_MODEL_CACHE=/app/.hf_cache \
    EASYOCR_MODULE_PATH=/app/.easyocr

WORKDIR /app

# opencv-python-headless still links these even with no display attached.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
 && rm -rf /var/lib/apt/lists/*

# The default torch wheel on PyPI carries the CUDA runtime with it: gigabytes of GPU code that
# a Railway container has no card to run. The CPU index serves the same torch without it.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.1.0"

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN python scripts/prefetch_models.py

EXPOSE 8080

# --timeout 300 because a twelve-claim post has taken 195 seconds; gunicorn's default of 30
# would kill every check IRIS makes. --threads 8 carries five devices with room over.
CMD gunicorn app:app \
      --bind "0.0.0.0:${PORT:-8080}" \
      --workers 1 \
      --threads 8 \
      --timeout 300 \
      --graceful-timeout 30 \
      --access-logfile -
