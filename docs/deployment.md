# Deployment — one image, one tag, one host

**Canonical S11 deployment document.** Single Docker image → Amazon ECR → one EC2 instance,
calling Bedrock through an **IAM instance role**. Iron rule: **secrets never enter the image,
the repository, a log, a compose file or a screenshot.**

> Status 2026-08-02: **deployed and verified.** Live at
> `http://ec2-35-91-36-186.us-west-2.compute.amazonaws.com:8501`, running ECR tag
> `2cd9b43`. Rollback has actually been executed. The one thing still missing is the
> 15-minute timed judged-flow rehearsal, which is a human task —
> see [Verified / not verified](#verified--not-verified).

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
| `HOYA_MARKET_CACHE_DIR` | no | local Binance daily-K cache, for example `/app/market_cache`; prepopulate with `scripts/prefetch_market_data.py` |
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

## 6. Continuous deployment (added 2026-08-02)

`.github/workflows/deploy.yml` automates §4–§5 after `.github/workflows/ci.yml`'s
`CI` workflow finishes successfully on `main` (`workflow_run`, filtered to
`conclusion == 'success'`), plus a manual `workflow_dispatch` for an ad-hoc
re-run. It builds the image tagged with the deployed commit's short SHA, pushes
to ECR, then drives the same SSM Run Command flow used by hand in §5 — pull,
rewrite `HOYA_IMAGE` in `/opt/hoya/deploy/.env`, `docker compose -p hoya -f
compose.https.yml up -d` — and finally runs `scripts/smoke_test.py` inside the
freshly swapped container. Any step failing (including the smoke test) fails
the job; the previous container keeps serving traffic until a swap actually
completes, since compose only recreates the `hoya-agent` service.

**Live deployment is `docker compose -p hoya`, not the bare `docker run` in
§5.** §5 predates the Caddy/HTTPS/basic-auth layer that now fronts the
instance; treat it as the conceptual shape (pull → swap → verify), not a
literal command to paste. `-p hoya` matters — running compose from
`/opt/hoya/deploy` without it creates a second stack that fights the first one
for port 443.

Credentials: IAM user `github-actions-hoya-deploy`, access key stored as the
encrypted repo secrets `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. Its
inline policy is scoped to exactly what the workflow needs — ECR push to the
`hoya-agent` repository only, `ssm:SendCommand` against this one EC2 instance
and the `AWS-RunShellScript` document only, `ssm:GetCommandInvocation` (no
resource-level restriction is possible for that action). Non-sensitive config
(`AWS_REGION`, `AWS_ACCOUNT_ID`, `ECR_REPO`, `EC2_INSTANCE_ID`) is stored as
repo variables, not secrets.

This account is a temporary Workshop Studio grant (see below) — when it is
reclaimed, this user and its key go with it. Rotate or delete the key from IAM
directly if the pipeline is ever retired before then; nothing else in the repo
references it.

Rollback stays a manual, deliberate action (§5's rollback section) — the
pipeline does not automatically roll back a failed deploy, it just refuses to
report success.

## 7. Optional cloud extensions (Task 21, added 2026-08-03)

Written when the Workshop Studio grant above was believed reclaimed and no live
AWS access was available to verify any of it end to end — see
`docs/Implementation-Plan.md` §9 Task 21. Each piece below is additive and
off by default; none of it is wired into `application.py` or the running
deployment.

- **S3 artifact mirroring** — `src/hoya_agent/adapters/s3_mirror.py::mirror_artifacts()`.
  Copies a completed run's already-written artifacts to S3 after the local
  write succeeds; never a dependency of artifact completion. Client is
  injectable (same pattern as `adapters/bedrock.py`), so it is fully unit
  tested (`tests/unit/data_evidence/test_s3_mirror.py`) without any AWS
  access. Not called from `application.py` — a future wiring would call it
  once `ApplicationService.run()` finishes and the run directory exists.
- **CloudWatch run metrics** — `src/hoya_agent/adapters/cloudwatch_metrics.py::emit_run_metrics()`.
  Publishes `RunCompleted` (dimensioned by terminal state), `RunDurationSeconds`
  and `EvidenceCount` to a `HoyaAgent` namespace. Same injectable-client
  pattern, same "never blocks the run it describes" guarantee, same
  not-yet-wired status.
- **ECS** — evaluated, not adopted. `deploy/ecs/task-definition.json` +
  `deploy/ecs/README.md` explain why (a single EC2 host already satisfies
  the one deployment guarantee this project actually needs) and give a
  ready-to-register Fargate task definition, consistent with the current
  `Dockerfile`/`compose.yaml`, for whenever migrating is actually decided.
  Verified for JSON syntax only — registering and running it needs real AWS
  access this session did not have.

## Known operational conditions

### ✅ Bedrock is enabled on account `411451203311`

The competition account is an **AWS Workshop Studio** account provided by the organizer, and
the Anthropic use case details form has already been submitted on it. Verified 2026-08-02
with `scripts/diagnose_bedrock.py` against `us.anthropic.claude-haiku-4-5-20251001-v1:0`:
**3/3 successful calls, ~8 s each.**

Two consequences of it being a Workshop Studio account:

- **Credentials are short-lived.** They come from the event's "Get AWS CLI credentials" panel
  and expire. Store them as a named profile with `aws_session_token`; refresh when the CLI
  starts returning `ExpiredToken`.
- **The account is temporary.** It is reclaimed when the event ends, so nothing here is
  durable infrastructure. Rebuild from §4 and §5 if it is reset.

### 🔴 Binance geo-blocks this EC2 instance — market evidence goes to zero

Verified 2026-08-02 from inside the running container: `curl` to
`https://api.binance.com/api/v3/ping` returns **HTTP 451** (Unavailable For
Legal Reasons). This is Binance's own geo-block on US-origin IPs, not a
network, DNS or security-group problem — `api.alternative.me` from the same
container returns `200` in the same test.

Binance is the sole designated live market baseline (tasks.md Task 4: on
baseline failure, emit an honest degraded gap rather than switching provider),
so on this host the Market Worker's live evidence is zero. Combined with
CryptoPanic returning `403` (no `CRYPTOPANIC_API_TOKEN` configured — an
accepted, disclosed gap by design), a live run here can be left with only the
Fear & Greed item (`low` reliability) as evidence, which yields a report like
"完成（含降級）", 1 evidence item, confidence `low` — not a crash, but not a
useful demonstration of the reasoning layer either.

This is a genuine infrastructure conflict, not something a code fix resolves:
Bedrock's `us.` inference profile requires this instance to stay in a US
region (see above), and Binance blocks US-origin IPs. **Accepted as a known
limitation for this deployment** rather than reworked before submission —
disclose it plainly if a judge runs a live query against this EC2 URL
directly. It does not affect `rehearsal`/`demo` fixture runs, and it does not
affect a local (地端) run from a non-US network, which is why the same
question can look fine on a laptop and degraded here.

### 🔴 A full evidence ledger can exhaust the Arbiter's 45-second call budget

Observed 2026-08-02 on two live runs from the same commit:

| Asset | Evidence items | Independence groups | Arbiter | Result |
|---|---:|---:|---|---|
| ETH | 6 | 2 | completed | conclusions, confidence `high` |
| BTC | 20 | 4 | `DeadlineExceeded` | **no conclusions**, 目前無法可靠判定 |

The inversion is the problem: **the better acquisition works, the larger the Arbiter prompt,
and the more likely the whole reasoning layer is lost.** BTC met the run target of three
source types and three independence groups and was then the one that failed.

The 45-second per-call cap is fixed by `competition-rules.md` and by `config.py`
(`LLM_CALL_TIMEOUT_SECONDS` hard max 45), so it cannot simply be raised. The levers that do
not touch the frozen `reasoning/` package are both on `ArbiterSettings`, which
`application.build_research_pipeline` and `composition.build_live_pipeline` construct:

- `max_evidence` (default 30) — fewer items, shorter prompt
- `max_tokens` (default 8000) — likely the larger factor, since generation time dominates

**Not changed here.** Tuning the reasoning stage is the reasoning owner's call and needs their
agreement under Feature Freeze. Until it is decided, expect a rich-evidence live run to be at
risk of losing its conclusions.

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
| ECR repository + push | ✅ | `hoya-agent`, IMMUTABLE, scanOnPush; tags `2cd9b43` and `c844a38` |
| EC2 deployment | ✅ | `i-000a2cdc6d3c1afab`, t3.small, us-west-2a |
| Public healthcheck | ✅ | `http://35.91.36.186:8501/_stcore/health` → `ok` |
| Deployed tag == pushed tag | ✅ | `docker inspect` → `…/hoya-agent:2cd9b43`, character for character |
| In-image smoke on EC2 | ✅ | four artifacts, 6 log events, 5 evidence, one `run_id` |
| Non-root + no `.env` on EC2 | ✅ | `uid=10001(appuser)`; `/app/.env` absent |
| Rollback rehearsal | ✅ | rolled back to `c844a38` (healthy 20 s), rolled forward to `2cd9b43` (healthy 20 s) |
| No SSH exposure | ✅ | security group opens 8501 only, to one source IP; administration via SSM |
| Recorded fallback saved outside VCS | ✅ | `C:\Users\USER\Documents\AWS\hoya-demo-fallback\run_20260802_015425_demo1` |
| CSV / Binance overlap check | ✅ | five assets, 31 days, 0.0000% close difference — see [live-source-check.md](rehearsals/live-source-check.md) |
| **15-minute timed rehearsal** | 🔴 **not executed** | human task; script in [demo-runbook.md](demo-runbook.md) |
| Live run with reasoning | 🔴 blocked | Bedrock account enablement, see above |

## Deployment record — 2026-08-02

| | |
|---|---|
| Account / region | `411451203311` / `us-west-2` |
| ECR | `411451203311.dkr.ecr.us-west-2.amazonaws.com/hoya-agent` — IMMUTABLE, scanOnPush |
| Deployed tag | `2cd9b43` (digest `sha256:a2d4e9c9…`), 201 MB compressed |
| Previous known-good tag | `c844a38` — kept in ECR as the rollback target |
| Instance | `i-000a2cdc6d3c1afab`, t3.small, AL2023 `ami-0b76d82b547c3c077`, 20 GB gp3 |
| Public URL | `http://ec2-35-91-36-186.us-west-2.compute.amazonaws.com:8501` |
| IAM instance role | `hoya-agent-ec2` — ECR read-only + SSM core + inline `bedrock:InvokeModel` |
| Security group | `sg-09d81b95b733a1a5a` — inbound tcp/8501 from `223.137.155.152/32` only. **No port 22.** |
| IMDS | `HttpTokens=required` (IMDSv2 enforced) |
| Credentials on host | none — instance role through the standard chain |

**Widen access for the judged run** by adding a source to the security group, and narrow it
again afterwards:

```bash
aws ec2 authorize-security-group-ingress --region us-west-2 \
  --group-id sg-09d81b95b733a1a5a --protocol tcp --port 8501 --cidr <judge-ip>/32
```

**Stop or terminate when the demo is over** — the instance bills while it runs:

```bash
aws ec2 stop-instances     --region us-west-2 --instance-ids i-000a2cdc6d3c1afab
aws ec2 terminate-instances --region us-west-2 --instance-ids i-000a2cdc6d3c1afab
```

## Pre-submission checklist

- [ ] image / repo / compose / log contain no key or token (`git ls-files` is clean)
- [ ] EC2 uses an IAM instance role; no access key on the machine
- [ ] container runs as non-root `appuser`
- [ ] security group opens only what is needed; port 22 stays closed
- [ ] any previously leaked key has been revoked and rotated
- [ ] screenshots and recordings contain no `.env`, credential or key
- [ ] the ECR tag and the running tag match character for character
- [ ] rollback has actually been executed once, and the log says so
