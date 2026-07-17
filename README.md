# HOYA BIT Hackathon AI Agent

HOYA BIT 2026 生成式 AI 應用黑客松原型：在限時內整合市場資料與外部證據，產出可追溯、可揭露限制的加密市場分析報告。

## Current Status

- Approved architecture: H2-Lite bounded specialist pipeline
- Orchestration: Python `asyncio`
- LLM: Amazon Bedrock Converse API
- UI: Streamlit
- Deployment target: Docker, Amazon ECR, and Amazon EC2
- Optional H3 debate: disabled and outside MVP scope

The approved source of truth is [the project design](docs/superpowers/specs/2026-07-17-hoya-bit-hackathon-agent-design.md). Kiro requirements, design, tasks, and steering files will be committed under `.kiro/` before implementation starts.

The approved four-person ownership, branch, handoff, and two-day execution rules are in [the team workflow](docs/superpowers/specs/2026-07-17-four-person-team-workflow-design.md).

## Repository Policy

Competition PDFs and ZIP archives remain local and are not committed. The extracted OHLCV CSV files are retained as reproducible rehearsal fixtures. Secrets must remain in local environment files or deployment secret stores.

This project produces research-oriented analysis and does not provide investment advice.
