# Deployment — one image, one tag, one host

**Canonical S11 deployment document.** Single Docker image → Amazon ECR → one EC2 instance,
calling Bedrock through an **IAM instance role**. Iron rule: **secrets never enter the image,
the repository, a log, a compose file or a screenshot.**

> Status: the local delivery layer below is **verified**; the ECR/EC2 section is the
> procedure and has **not been executed yet**. Nothing here claims otherwise —
> see [Verified / not verified](#verified--not-verified) at the end.

## Environment variables

Names only. No values appear in this repository. `run_config.json` records key *presence*
as a boolean and never a value.

| Variable | Required | Notes |
|---|---|---|
| `AWS_REGION` | for Bedrock | `us-west-2`. The `us.` inference profiles are US-region only, so keep this at `us-west-2` even if the host lives elsewhere. |
| `BEDROCK_PRIMARY_MODEL_ID` | for reasoning | e.g. an `us.anthropic.claude-haiku-4-5-…` inference profile id. Unset → live mode still runs, with deterministic evidence and no conclusions. |
| `BEDROCK_FALLBACK_MODEL_ID` | no | throttling fallback |
| `CRYPTOPANIC_API_TOKEN` | no | degrades to a disclosed gap without it |
| `HOYA_DATA_DIR` | no | set inside the image to `/app/HOYA_BIT_crypto_market_dataset/data` |
| `ARTIFACT_ROOT` | no | only read by `Settings.from_env`; the UI writes to a per-run temp dir |

Credentials themselves come from the standard AWS chain — an instance role on EC2, a
profile locally. **Never** `AWS_ACCESS_KEY_ID` on the host.

## 1. Local gate (run this before touching AWS)

```bash
python -m pytest tests/unit tests/contract tests/integration tests/acceptance -m "not live" -q
ruff check .
docker compose config
git status --short
```

Then the image itself:

```bash
TAG=$(git rev-parse --short HEAD)
docker build -t hoya-agent:$TAG .
docker run -d --rm -p 8501:8501 --name hoya-agent hoya-agent:$TAG
curl -f http://localhost:8501/_stcore/health          # → ok
```

**The smoke test must run inside the container.** The Streamlit UI writes its artifacts to a
per-run temporary directory that no host process can see, so a host-side run would prove the
host's code rather than the image's. `scripts/` is excluded by `.dockerignore`, hence the copy:

```bash
docker cp scripts/smoke_test.py hoya-agent:/tmp/smoke_test.py
docker exec hoya-agent python /tmp/smoke_test.py --base-url http://localhost:8501
```

Expected: HTTP health `ok`, the app root serving Streamlit HTML, four fixed artifacts written,
every artifact parsing, and **all four carrying the same `run_id`**.

Security spot-checks:

```bash
docker exec hoya-agent id                              # → uid=10001(appuser)
docker exec hoya-agent sh -c 'ls -A /app/.env 2>&1'    # → No such file or directory
```

## 2. Secret scan

CI runs this on every push (`.github/workflows/ci.yml`, job `secret-scan`). To reproduce locally:

```bash
# Scan what the repository actually ships — not the checkout directory. Scanning the
# whole directory also sweeps the installed dependency tree, whose own test fixtures
# are full of example keys; that produced 125 findings, none of them ours.
mkdir -p /tmp/tracked && git archive HEAD | tar -x -C /tmp/tracked
docker run --rm -v /tmp/tracked:/repo ghcr.io/gitleaks/gitleaks:v8.28.0 \
  dir /repo --no-banner --redact --exit-code 1

# Full history, run once before submission
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:v8.28.0 git /repo --no-banner --redact

git ls-files | grep -E '(^|/)\.env$|\.pem$|\.key$|\.p12$|secrets\.toml$'   # must print nothing
```

**Result 2026-08-02 (gitleaks v8.28.0):** tracked content 315 files → *no leaks found*;
full history 206 commits → *no leaks found*.

## 3. IAM instance role

Attached to the EC2 instance. **No access key is created, stored or rotated.**

| Policy | Why |
|---|---|
| `AmazonEC2ContainerRegistryReadOnly` | pull the image from ECR |
| `AmazonSSMManagedInstanceCore` | administration without opening SSH |
| inline `InvokeBedrockModels` (below) | the reasoning layer |

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

## 4. ECR

```bash
AWS_REGION=us-west-2
ACCOUNT_ID=<account-id>
REPO=hoya-agent
TAG=$(git rev-parse --short HEAD)      # immutable: this tag *is* the commit

aws ecr create-repository --repository-name $REPO --region $AWS_REGION \
  --image-tag-mutability IMMUTABLE --image-scanning-configuration scanOnPush=true

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker tag hoya-agent:$TAG $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:$TAG
docker push $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$REPO:$TAG
```

Write `$TAG` down. **The tag EC2 runs must be character-for-character the tag that was pushed.**

## 5. EC2

- One `t3.small`, Amazon Linux 2023, `us-west-2`, Docker + compose plugin installed.
- IAM instance profile from §3 attached.
- **Security group: port 22 is not opened.** Administration is SSM Session Manager. Port 8501
  is restricted to known source IPs, widened only for the rehearsal and the judging window.

```bash
AWS_REGION=us-west-2
ACCOUNT_ID=<account-id>
TAG=<the tag from §4>
IMAGE=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hoya-agent:$TAG

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
docker pull $IMAGE

docker run -d --restart unless-stopped -p 8501:8501 --name hoya-agent \
  -e AWS_REGION=$AWS_REGION \
  -e BEDROCK_PRIMARY_MODEL_ID=<inference-profile id> \
  $IMAGE
```

No credential is passed. The container resolves the instance role through the standard chain.

### Verify

```bash
curl -f http://localhost:8501/_stcore/health                       # on the host
curl -f http://<ec2-public-dns>:8501/_stcore/health                # from outside
docker cp scripts/smoke_test.py hoya-agent:/tmp/ && \
  docker exec hoya-agent python /tmp/smoke_test.py --base-url http://localhost:8501
docker inspect --format '{{.Config.Image}}' hoya-agent             # must equal $IMAGE
```

Then open `http://<ec2-public-dns>:8501`, pick an asset, choose 即時 official, and run.

### Rollback

Rehearse it once; an untested rollback is not a rollback.

```bash
docker rm -f hoya-agent
docker run -d --restart unless-stopped -p 8501:8501 --name hoya-agent \
  -e AWS_REGION=$AWS_REGION -e BEDROCK_PRIMARY_MODEL_ID=<inference-profile id> \
  $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/hoya-agent:<previous known-good tag>
curl -f http://localhost:8501/_stcore/health
```

## Known operational conditions

### 🔴 Bedrock is not enabled on account `035741228337`

Every Converse call from this account in `us-west-2` returns:

```
ResourceNotFoundException: Model use case details have not been submitted for this account.
Fill out the Anthropic use case details form before using the model.
```

Reproduced 2026-08-02 with `scripts/diagnose_bedrock.py` against Haiku 4.5, Claude 3 Haiku and
Sonnet 4.5, `us.` and `global.` profiles — 0/3 successful calls each. This is an **account
enablement action in the Bedrock console**, not a defect.

Until it is submitted and propagated, a deployment still works and is still honest: the report
carries deterministic market evidence, discloses that reasoning was unavailable, and ships four
artifacts. It simply has no inference or conclusion Claims. Do not present such a run as a full
Silver/Gold demonstration.

### Image size

860 MB (pandas + streamlit + boto3 + pyarrow). Pull once on the host before the rehearsal;
do not leave the first pull to the judged window.

## Verified / not verified

| | Status | Evidence |
|---|---|---|
| Non-live suite + Ruff | ✅ 2026-08-02 | 1266 passed; All checks passed! |
| `docker compose config` | ✅ | VALID |
| Image build | ✅ | `hoya-agent:c844a38`, 860 MB |
| Local container healthcheck | ✅ | `Up (healthy)`, `/_stcore/health` → `ok` |
| In-image smoke test | ✅ | four artifacts, 6 log events, 5 evidence items, one `run_id` |
| Non-root, no `.env` in image | ✅ | `uid=10001(appuser)`; `/app/.env` absent |
| Secret scan | ✅ | tracked 315 files and 206 commits, no leaks |
| CI | ✅ | all three jobs green on first run |
| ECR repository + push | 🔴 not executed | — |
| EC2 deployment | 🔴 not executed | — |
| Public healthcheck | 🔴 not executed | — |
| Rollback rehearsal | 🔴 not executed | — |
| 15-minute timed rehearsal | 🔴 not executed | see [demo-runbook.md](demo-runbook.md) |

## Pre-submission checklist

- [ ] image / repo / compose / log contain no key or token (`git ls-files` is clean)
- [ ] EC2 uses an IAM instance role; no access key on the machine
- [ ] container runs as non-root `appuser`
- [ ] security group opens only what is needed; port 22 stays closed
- [ ] any previously leaked key has been revoked and rotated
- [ ] screenshots and recordings contain no `.env`, credential or key
- [ ] the ECR tag and the running tag match character for character
- [ ] rollback has actually been executed once, and the log says so
