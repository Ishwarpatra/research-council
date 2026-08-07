# Stage 1: Build the React frontend SPA
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend-build
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
ENV VITE_API_WSS_URL=/api/ws
ENV VITE_API_REST_URL=/api
RUN npm run build

# Stage 2: Build python dependencies in a builder container
FROM python:3.13-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
RUN python -c "import tomllib; open('reqs.txt', 'w').write('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r reqs.txt

# Stage 3: Minimal runtime image serving both ASGI server and static assets
FROM python:3.13-slim AS runtime
WORKDIR /app
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application backend code
COPY . .

# Copy compiled frontend assets from frontend-builder stage into frontend/dist
COPY --from=frontend-builder /frontend-build/dist ./frontend/dist

# Expose port and run API server
EXPOSE 8080
CMD ["python", "council.py", "--api"]
