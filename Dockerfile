FROM python:3.9-slim
WORKDIR /app

# Install system dependencies + CA Certificates to ensure SSL works
RUN apt-get update && apt-get install -y \
    gcc g++ ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Use a very long timeout and the trusted-host bypass
RUN pip install --no-cache-dir \
    --upgrade pip \
    --timeout 120 \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]