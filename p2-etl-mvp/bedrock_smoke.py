"""One-shot Bedrock 連通測試。設好環境變數後執行：python bedrock_smoke.py

需要（同一個終端機視窗）：
  AWS_REGION            例：us-west-2
  BEDROCK_MODEL_ID      從 Bedrock 模型目錄複製的 Claude model id
  AWS_BEARER_TOKEN_BEDROCK  你的 Bedrock 金鑰（或用 IAM 角色 / 臨時憑證）
"""

from __future__ import annotations

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from reasoning.bedrock_client import BedrockClient

model_id = os.getenv("BEDROCK_MODEL_ID")
region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-west-2"
has_cred = bool(os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("AWS_ACCESS_KEY_ID"))

print(f"region = {region}")
print(f"model  = {model_id or '(未設)'}")
print(f"憑證   = {'偵測到' if has_cred else '未偵測到(若用 IAM 角色可忽略)'}")

if not model_id:
    print("\n[X] 未設 BEDROCK_MODEL_ID —— 去 Bedrock『模型目錄』點 Claude 複製它的 model id")
    sys.exit(1)

try:
    llm = BedrockClient()
    out = llm.complete(system="Reply with exactly the two letters: OK", user="ping")
    print(f"\n[OK] Bedrock 有回應：{out[:200]!r}")
    print("→ 連通成功，可以跑 python run_live.py BTC 了")
except Exception as exc:  # noqa: BLE001 - smoke test surfaces any failure
    msg = str(exc)
    print(f"\n[ERR] {type(exc).__name__}: {msg[:500]}")
    if "inference profile" in msg or "on-demand" in msg or "isn't supported" in msg.lower():
        print("→ 這顆模型需要 inference profile：把 model id 前面加 'us.' 再試")
        print(f"   例如 BEDROCK_MODEL_ID = us.{model_id}")
    elif "AccessDenied" in msg or "not authorized" in msg or "don't have access" in msg.lower():
        print("→ 沒有模型存取權：去『模型目錄 / 模型存取』對這顆 Claude 按 request/開通")
    elif "ExpiredToken" in msg or "security token" in msg.lower() or "Unauthorized" in msg:
        print("→ 金鑰過期/無效：重新產一把 Bedrock 金鑰再設 AWS_BEARER_TOKEN_BEDROCK")
    elif "Could not connect" in msg or "EndpointConnectionError" in msg:
        print("→ region 不對或無網路：確認 AWS_REGION=us-west-2")
    elif "No module named 'boto3'" in msg:
        print("→ 先安裝：pip install boto3")
    sys.exit(2)
