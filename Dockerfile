# Stage 1: Build dependencies in a temporary container
FROM python:3.13-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .

# Install dependencies into a wheels directory to avoid copying compile tooling to runtime
RUN python -c "import tomllib; open('reqs.txt', 'w').write('\n'.join(tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']))" && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r reqs.txt

# Stage 2: Minimal, clean, and secure runtime image
FROM python:3.13-slim AS runtime

WORKDIR /app

# Copy compiled wheels from builder
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application code
COPY . .

# Expose port and run API server microservice
EXPOSE 8080
CMD ["python", "council.py", "--api"]
