# ECS task definition — evaluated, not adopted (Task 21)

**Current deployment stays one EC2 host + `docker compose`** (see
`docs/deployment.md`) — that is deliberate, not an oversight. This directory
is the "ready to deploy later" artifact Task 21 asks for: a Fargate task
definition consistent with the running Dockerfile/`compose.yaml`, checked in
so migrating is a known, bounded amount of work whenever it is actually
decided, not a from-scratch design exercise.

## Why ECS was evaluated and not adopted now

- The project's one hard deployment guarantee (`docs/deployment.md` §5,
  Task 10) is: the ECR tag pushed and the tag running are character-for-character
  identical, on one host, with rollback rehearsed. A single EC2 instance
  already satisfies that guarantee completely; ECS's main benefits (rolling
  deploys across multiple tasks, auto-scaling, service discovery) all address
  problems this project does not have — one Streamlit app process, one judge
  session at a time.
- No live AWS access was available in the session that wrote this template
  (see `docs/Implementation-Plan.md` §9 Task 21), so it could not be
  registered or run — only validated for JSON syntax
  (`python -c "import json; json.load(open('task-definition.json'))"`,
  passes) and cross-checked field-by-field against `Dockerfile`/`compose.yaml`.
  Migrating a live, working single-host deployment to a new orchestrator
  without being able to verify the result end to end would be a strictly
  worse trade than leaving EC2 running and shipping this template for later.

## What is in `task-definition.json`

- `awsvpc` networking, Fargate, port 8501 (matches `compose.yaml`).
- The same environment variable names `compose.yaml` already reads:
  `HOYA_DATA_DIR`, `AWS_REGION`, `BEDROCK_PRIMARY_MODEL_ID`,
  `BEDROCK_FALLBACK_MODEL_ID`. Placeholder values only — fill in at deploy
  time, never commit real ones.
- The same healthcheck command the `Dockerfile` already uses.
- `awslogs` log driver targeting `/ecs/hoya-agent` — this is the natural
  place CloudWatch Logs enters an ECS deployment; a plain EC2 host would
  instead need the CloudWatch agent installed and configured separately
  (not attempted here, since it is deployment-host configuration, not
  application code, and would need to be verified against the actual
  running instance).
- `executionRoleArn`/`taskRoleArn` placeholders — mirror the existing EC2
  instance role's policies (`docs/deployment.md` §3: ECR read, Bedrock
  invoke) rather than inventing new ones. No access key anywhere, same rule
  as the EC2 path.

## To actually use this later

1. Fill in `<ACCOUNT_ID>`, `<AWS_REGION>`, `<TAG>` (an already-pushed ECR
   tag — same immutable-tag rule as the EC2 path), and the two Bedrock
   model id placeholders.
2. Create `executionRoleArn`/`taskRoleArn` (or reuse policy documents from
   `docs/deployment.md` §3) and a `/ecs/hoya-agent` log group.
3. `aws ecs register-task-definition --cli-input-json file://task-definition.json`
4. Create a cluster + Fargate service pointing at this task definition,
   with a security group that only opens 8501 to the intended source — the
   same restriction `docs/deployment.md` §5 already applies to the EC2 host.
5. Smoke-test with `scripts/smoke_test.py` against the new service's
   endpoint, exactly as already done for EC2.

Steps 3-5 need real AWS access this session did not have; nothing past step 1
(JSON syntax) has been verified.
