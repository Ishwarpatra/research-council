# Containerized microservice definition for Research Consensus Council
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy python project definition
COPY pyproject.toml .

# Install dependencies using pip (pyproject.toml defines project metadata)
RUN pip install --no-cache-dir .

# Copy source tree
COPY . .

# Default service port
EXPOSE 8080

# Run API server microservice
CMD ["python", "council.py", "--api"]
