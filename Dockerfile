FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY backend ./backend

WORKDIR /app/backend

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["python demo_showcase_seed.py && python demo_showcase_patch.py && exec uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]
