# STAGE 1: Builder
FROM python:3.9-slim as builder
WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y gcc g++ ca-certificates && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install packages to a local folder
# Added --only-binary to speed up and avoid compilation where possible
RUN pip install --user --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# STAGE 2: Final Runtime
FROM python:3.9-slim
WORKDIR /app

# Copy only the installed packages from the builder
COPY --from=builder /root/.local /root/.local
COPY . .

# Update Path to find installed packages
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]