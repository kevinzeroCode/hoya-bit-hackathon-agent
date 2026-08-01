# HOYA P2 — 資料/證據層 + Streamlit 前端
#
# 建置(從 repo 根目錄執行,才能一起打包官方資料集):
#   docker build -f p2-etl-mvp/Dockerfile -t hoya-p2 .
# 執行(Bedrock 用金鑰;EC2 上改用 IAM 角色則免傳這些):
#   docker run --rm -p 8501:8501 \
#     -e AWS_REGION=us-west-2 \
#     -e BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
#     -e AWS_BEARER_TOKEN_BEDROCK=... \
#     hoya-p2
# 開 http://localhost:8501

FROM python:3.12-slim

WORKDIR /app
# 程式碼(p2-etl-mvp/ 內容 → /app)
COPY p2-etl-mvp/ /app/
# 官方資料集 → /app/data,並用環境變數指定(避免相對路徑脆弱)
COPY HOYA_BIT_crypto_market_dataset/data/ /app/data/
ENV HOYA_DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 相依:httpx + boto3(Bedrock)+ streamlit(ui)
RUN pip install -e ".[ui]"

EXPOSE 8501
# 容器內健康檢查(Streamlit 內建端點)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8501/_stcore/health'); " || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
