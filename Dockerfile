FROM python:3.9-slim
WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ ca-certificates && update-ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# No-cache and trusted-host ensure we don't use a broken cached layer
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY . .
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
CMD ["python", "src/main.py"]