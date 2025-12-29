FROM python:3.9-slim
WORKDIR /app

# Combine updates and installs into one layer to save space
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Use --no-cache-dir to prevent pip from storing download history
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
CMD ["python", "src/main.py"]