FROM python:3.9-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies with trusted hosts
# We use --network=host in the build command, so this should fly now
RUN pip install --no-cache-dir \
    --timeout 100 \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
CMD ["python", "src/main.py"]