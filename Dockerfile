FROM python:3.9-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 1. Upgrade pip first (Bypassing SSL)
# 2. Install requirements with a longer timeout and trusted hosts
RUN pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org && \
    pip install --no-cache-dir \
    --timeout 100 \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]