# Hugging Face Space (Docker) image: FastAPI + the built React app + Chromium for PDF export.
# Hugging Face runs the container as user 1000 and routes traffic to port 7860.

# ---- 1. build the frontend
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2. runtime
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app

COPY requirements.txt requirements-space.txt ./
RUN pip install -r requirements.txt -r requirements-space.txt \
    && playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright

RUN useradd -m -u 1000 user
COPY --chown=user . /app
COPY --from=web --chown=user /web/dist /app/frontend/dist
RUN mkdir -p /app/outputs && chown -R user /app/outputs
USER user

ENV OUTPUTS_DIR=/app/outputs FRONTEND_DIST=/app/frontend/dist HOME=/home/user
EXPOSE 7860
CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "7860", "--proxy-headers", "--forwarded-allow-ips", "*"]
