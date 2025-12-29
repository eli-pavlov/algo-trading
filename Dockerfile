FROM python:3.11-slim
WORKDIR /app

# Combine apt install and clean up in one layer to save space
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip first and install requirements
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    --timeout 100 \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1
CMD ["python", "src/main.py"]