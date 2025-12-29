version: '3.8'
services:
  trading-bot:
    build: .
    container_name: algo_heart
    restart: always
    env_file: .env
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD-SHELL", "find /tmp/heartbeat -mmin -2 | grep . || exit 1"]
      interval: 1m
      retries: 3

  dashboard:
    build: .
    container_name: algo_ui
    ports:
      - "8501:8501"
    env_file: .env
    volumes:
      - ./data:/app/data
    command: streamlit run src/dashboard.py --server.port=8501 --server.address=0.0.0.0