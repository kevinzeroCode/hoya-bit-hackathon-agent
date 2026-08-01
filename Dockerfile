# HOYA Market Agent — Streamlit Bronze UI (S3)
#
# 建置(從 repo 根)：docker build -t hoya-agent .
# 執行(Bronze 離線,無需任何金鑰)：docker run --rm -p 8501:8501 hoya-agent
# 開 http://localhost:8501
#
# Silver+（接 Bedrock）時再傳: -e AWS_REGION=us-west-2 -e BEDROCK_MODEL_ID=... -e AWS_BEARER_TOKEN_BEDROCK=...

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# 套件安裝(hatchling: packages=src/hoya_agent;含 httpx/boto3/streamlit)
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e .

# 官方資料集(Bronze 離線用),用環境變數指定路徑
COPY HOYA_BIT_crypto_market_dataset ./HOYA_BIT_crypto_market_dataset
ENV HOYA_DATA_DIR=/app/HOYA_BIT_crypto_market_dataset/data

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "src/hoya_agent/ui/streamlit_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
