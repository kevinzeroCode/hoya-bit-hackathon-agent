# HOYA AWS 架構圖

這是 HOYA Market Agent 目前 MVP 的雲端部署架構。實線是目前的部署路徑；虛線是刻意排除在 MVP 外的未來擴充。

```mermaid
flowchart LR
    Dev["Developer"] -->|push main| GH["GitHub Repository"]

    subgraph Actions["GitHub Actions"]
        CI["CI\nRuff + pytest + Docker smoke + secret scan"]
        OIDC["GitHub OIDC\nshort-lived AWS session"]
    end

    GH --> CI
    CI -->|success| OIDC
    OIDC -->|assume deploy role| ECR["Amazon ECR\nimmutable commit-SHA image"]
    OIDC -->|SSM send-command| SSM["AWS Systems Manager\nSession Manager / Run Command"]

    subgraph AWS["AWS us-west-2"]
        subgraph Host["Single EC2 instance · t3.small · Amazon Linux 2023"]
            Role["IAM instance role\nECR read + SSM + Bedrock invoke"]
            Docker["Docker container\nnon-root appuser"]
            UI["Streamlit :8501\nHOYA Market Agent"]
            Artifacts["Local artifact volume\n4 files per run"]
            Role --> Docker
            Docker --> UI
            UI --> Artifacts
        end

        ECR -->|docker pull exact SHA tag| Docker
        SSM -->|deploy / health check / rollback| Docker
        Docker -->|IAM role, no access keys| Bedrock["Amazon Bedrock\nConverse API"]
    end

    Judge["Judge browser"] -->|HTTP :8501\nSecurity Group allowlist| UI
    UI -->|HTTPS| Sources["Live sources\nBinance · RSS · Google News\nAlternative.me · official feeds"]

    Future["S3 / CloudWatch / ECS / ALB\nFuture, not MVP"] -.-> AWS
```

## Runtime data path

```text
Judge question + asset
        ↓
Streamlit / ApplicationService
        ↓
Plan → Market Worker ‖ Research Agent
        ↓
Evidence Processor → Evidence Ledger
        ↓
Arbiter → deterministic Renderer
        ↓
Local artifact volume
```

## Deployment guarantees

- 每次部署使用 commit SHA 作為 immutable ECR tag。
- EC2 只從 ECR 拉取該精確 tag；health check 失敗會 rollback。
- Bedrock 權限透過 EC2 IAM instance role 取得，不把長期 AWS access key 放入 image 或 repository。
- GitHub Actions 使用 OIDC，不保存長期 AWS credentials。
- EC2 透過 SSM 管理，不需要開 SSH port 22。
- Container 以 non-root user 執行，artifact 寫入本機 volume。

## MVP 邊界

目前刻意不使用 S3、CloudWatch、ECS、ALB、queue、database、Redis 或 horizontal scaling。MVP 是單一 EC2、單一 container，同時間只保證一個 active run。

詳細部署步驟請見 [`deployment.md`](deployment.md)；系統與 pipeline 設計請見 [`system-design.md`](system-design.md)。
