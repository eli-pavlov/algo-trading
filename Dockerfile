FROM python:3.9-slim
WORKDIR /app

# 1. Install system-level dependencies (Cached)
RUN apt-get update && apt-get install -y gcc g++ ca-certificates && \
    update-ca-certificates && rm -rf /var/lib/apt/lists/*

# 2. Copy ONLY the requirements file first (Cached)
COPY requirements.txt .

# 3. Install Python packages (This layer is now cached!)
# Docker will ONLY re-run this if requirements.txt changes
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# 4. Copy the rest of your code (Changes frequently)
COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]