FROM python:3.9-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc g++ ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Use extra trusted-host flags and a longer timeout
RUN pip install --no-cache-dir \
    --timeout 100 \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .
ENV PYTHONPATH=/app
CMD ["python", "src/main.py"]