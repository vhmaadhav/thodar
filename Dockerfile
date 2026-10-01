# Thodar in one container: Next.js on $PORT (default 7860, Hugging Face Spaces) proxying /api/* to
# FastAPI on 127.0.0.1:8000. Demo data is synthetic and regenerated at every start.
#
#   docker build -t thodar . && docker run -p 7860:7860 thodar
#   (optional) -e THODAR_SARVAM_API_KEY=... to enable live Tamil voice notes and photo import

FROM node:22-slim AS web
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_PUBLIC_API_URL=/api API_INTERNAL_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build && cp -r public .next/standalone/ && cp -r .next/static .next/standalone/.next/

FROM node:22-slim
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PORT=7860 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY --from=web /app/.next/standalone /app/web
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh && useradd -m thodar && chown -R thodar /app
USER thodar
EXPOSE 7860
CMD ["/app/start.sh"]
