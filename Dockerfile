FROM python:3.9-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Set PYTHONPATH so 'import src.database' works from anywhere
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
CMD ["python", "src/main.py"]