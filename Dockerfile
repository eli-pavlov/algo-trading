FROM python:3.9-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# FIX: Add trusted-host to bypass the SSL expiry error
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
CMD ["python", "src/main.py"]