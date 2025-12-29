FROM python:3.9-slim as builder
WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Use a specific index URL and bypass SSL checks completely
RUN pip install --user --no-cache-dir \
    --index-url https://pypi.org/simple \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    --trusted-host pypi.python.org \
    -r requirements.txt || \
    pip install --user --no-cache-dir \
    --index-url http://pypi.doubleu.top/simple \
    --trusted-host pypi.doubleu.top \
    -r requirements.txt

FROM python:3.9-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH PYTHONPATH=/app PYTHONUNBUFFERED=1
CMD ["python", "src/main.py"]