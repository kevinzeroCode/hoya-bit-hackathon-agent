# EC2 部署指南(單台 EC2 + ECR + Bedrock)

> 目標:單一 Docker image → ECR → 一台 EC2,用 **IAM instance role**(零金鑰)呼叫 Bedrock。
> 對應 `Implementation-Plan.md` S11。**鐵則:秘密永不進 image / repo / log / compose 檔。**

## 0. 前置
- EC2(建議 t3.small 以上、Amazon Linux 2023,已裝 Docker + docker compose plugin)。
- 一個 ECR repository。
- EC2 掛一個 **IAM instance role**,含 Bedrock 呼叫權限(見 §1)。
- 已在同 region 開通 Bedrock 對應模型的存取。

## 1. IAM 權限(掛在 EC2 instance role 上)
最小權限,**不需要任何 access key**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "InvokeBedrockModels",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": "*"
    }
  ]
}
```
> ECR pull 另需 `AmazonEC2ContainerRegistryReadOnly`(或等效)掛在同一 role。

## 2. 建置並推上 ECR(本機或 CI)
```bash
AWS_REGION=us-west-2
ACCOUNT_ID=<your-account-id>
REPO=hoya-agent
TAG=$(git rev-parse --short HEAD)     # immutable tag = 這次 commit

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker build -t $REPO:$TAG .
docker tag $REPO:$TAG $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:$TAG
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:$TAG
```
> **S11 要求**:推上去的 tag 與 EC2 實際跑的 tag **逐字相同**。記下 `$TAG`。

## 3. 在 EC2 上執行(IAM role,零金鑰)
```bash
AWS_REGION=us-west-2
ACCOUNT_ID=<your-account-id>
TAG=<剛剛那個 tag>

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
docker pull $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hoya-agent:$TAG

docker run -d --rm -p 8501:8501 \
  -e AWS_REGION=$AWS_REGION \
  -e BEDROCK_PRIMARY_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --name hoya-agent \
  $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hoya-agent:$TAG
```
- **沒有任何金鑰**:容器沿用 EC2 instance metadata 的 IAM role 憑證(boto3 標準鏈自動解析)。
- 設了 `AWS_REGION` + `BEDROCK_PRIMARY_MODEL_ID` → **即時模式啟用 Bedrock 推理(報告有結論)**。
- 沒設這兩個 → 即時模式只出決定論證據(Binance + 情緒),仍是誠實可 demo 的報告。

## 4. 驗證
```bash
curl -f http://localhost:8501/_stcore/health      # 應回 ok
```
瀏覽器開 `http://<EC2-public-DNS>:8501`(Security Group 開 8501)→ 選幣種 + 「即時 official」→ 執行分析。
- 有 Bedrock 權限:報告有推論/結論 + 信任漏斗 + 多來源。
- Bedrock 失敗/無權限:自動降級成「資料不足」誠實報告,**不會崩**。

## 5. Rollback(S11 要求演練一次)
```bash
docker stop hoya-agent
docker run -d --rm -p 8501:8501 -e AWS_REGION=$AWS_REGION \
  -e BEDROCK_PRIMARY_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --name hoya-agent \
  $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hoya-agent:<上一個已知良好 tag>
```

## 6. 安全清單(交付前逐項確認)
- [ ] image / repo / compose / log **沒有任何金鑰或 token**(`git ls-files` 不含憑證)。
- [ ] EC2 用 **IAM instance role**,不在機器上放 access key。
- [ ] 容器以 **非 root(appuser)** 執行(Dockerfile 已設)。
- [ ] Security Group 只開必要 port(8501,建議限來源 IP)。
- [ ] 先前若曾外流的 OpenAI / Bedrock 金鑰**已撤銷輪替**。
- [ ] 截圖 / 錄影不含 `.env`、憑證、金鑰。

## 7. 目前狀態與界線(誠實)
- **即時資料 + Bedrock 推理**:程式已就緒;**真結論需 IAM role 有 Bedrock 權限**才會出現。
- **新聞抽取(Planner + Research + RSS)**:尚未接(下一步);目前多源 = 市場 + 情緒。
- 這不是「完整 Silver Exit 已通過」——live gate(`RUN_LIVE_TESTS=1`)要在有憑證的環境跑過才算。
