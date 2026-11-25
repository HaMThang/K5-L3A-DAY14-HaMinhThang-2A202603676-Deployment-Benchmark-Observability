# Deployment Information

## Public URL

Not deployed yet. No public service URL has been issued.

## Platform

Railway is the configured target (`06-lab-complete/railway.toml`, Dockerfile builder and `/health` health check). A Railway service and Redis instance still need to be created and deployed.

## Test Commands

Replace `<PUBLIC_URL>` with the Railway URL after deployment. Set `AGENT_API_KEY` in the shell without committing its value.

### Health Check

```bash
curl -i https://<PUBLIC_URL>/health
# Expected: HTTP 200 and {"status":"ok"}
```

### API Test (with authentication)

```bash
curl -i -X POST https://<PUBLIC_URL>/ask \
  -H "X-API-Key: ${AGENT_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","question":"Hello"}'
# Expected: HTTP 200 with question and answer fields
```

## Environment Variables

Set these in Railway's service variables; do not commit secret values:

- `PORT` — supplied by Railway
- `REDIS_URL` — private connection URL for the Railway Redis service
- `AGENT_API_KEY` — generate a strong secret in Railway
- `LOG_LEVEL` — for example, `INFO`
- `ENVIRONMENT` — `production`
- `RATE_LIMIT_PER_MINUTE` — for example, `10`
- `DAILY_BUDGET_USD` — for example, `1.0`

## Screenshots

- Deployment dashboard: not captured; service has not been deployed.
- Service running: not captured; service has not been deployed.
- Test results: not captured for a public service. Local production-readiness results are recorded in `MISSION_ANSWERS.md`.
