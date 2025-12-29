FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for TA-Lib or other math libs if needed
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV DB_PATH=/app/data/trading.db

# Command overridden by docker-compose
CMD ["python", "src/main.py"]