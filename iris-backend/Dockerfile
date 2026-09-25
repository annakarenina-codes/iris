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
#
# torchvision comes from that same index, in the same command, pinned beside it. easyocr
# depends on torchvision, so letting requirements.txt fetch it separately got a PyPI build
# compiled against a different torch, and importing it failed with "operator torchvision::nms
# does not exist". The two are a matched pair or they are nothing.
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.13.0+cpu" "torchvision==0.28.0+cpu"

COPY requirements.txt .

# The same pins are repeated as constraints so that nothing in requirements.txt can quietly
# swap one half of the pair for a PyPI build, and the CPU index is offered alongside PyPI so
# the pinned versions stay findable if pip does decide to touch them.
RUN printf 'torch==2.13.0+cpu\ntorchvision==0.28.0+cpu\n' > /tmp/torch-pins.txt \
 && pip install --extra-index-url https://download.pytorch.org/whl/cpu -c /tmp/torch-pins.txt -r requirements.txt

# Fails here, cheaply and legibly, if the pair ever comes apart. Importing torchvision is what
# registers its operators against torch, so a mismatch surfaces now rather than part-way
# through a model download several minutes later.
RUN python -c "import torch, torchvision; print('torch', torch.__version__, '/ torchvision', torchvision.__version__)"

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
