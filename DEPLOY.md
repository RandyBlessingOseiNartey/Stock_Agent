# Deploying StockAgent (demo link)

One container serves the API **and** the built UI on a single port, so a
deployment is one service and one URL — no CORS, no separate frontend host.

```bash
docker build -t stockagent .
docker run --rm -p 8000:8000 --env-file .env stockagent   # → http://localhost:8000
```

---

## What this app actually needs (measured, not estimated)

| | Value |
|---|---|
| Image size | ~900 MB |
| Python deps installed | 290 MB (slimmed from 795 MB) |
| Cold start | ~20–25 s (OpenBB's interface is prebuilt into the image) |
| Memory, idle | **382 MiB** |
| Memory, peak during a 2-tool Terminal run | **498 MiB** |
| Longest request | Deep Research, ~3 minutes of streaming |

Two consequences:

1. **512 MB tiers are not viable.** A small run already peaks at 498 MiB.
   A Deep Research run or a second concurrent visitor will OOM. That rules
   out Render free, Koyeb free, and Fly's smallest instances.
2. **The platform must allow long streaming responses.** Anything with a
   30–60 s request cap will cut Deep Research off mid-report.

**Give the container 1 GB and a request timeout of at least 5 minutes.**

---

## Recommended: Google Cloud Run

Free monthly allowance (2M requests, 180k vCPU-s, 360k GiB-s) comfortably
covers a demo; it scales to zero when idle. A billing account with a card is
required, but the card isn't charged inside the allowance.

```bash
# One-time setup
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com

# Deploy straight from this directory — Cloud Build builds the Dockerfile
gcloud run deploy stockagent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 900 \
  --concurrency 4 \
  --max-instances 2 \
  --set-env-vars "OLLAMA_API_KEY=...,TAVILY_API_KEY=...,GOOGLE_API_KEY=...,DATABASE_URL=postgresql+asyncpg://..."
```

It prints a `https://stockagent-*.run.app` URL — that's the demo link.

Why those flags:

- `--memory 1Gi` — headroom over the 498 MiB peak.
- `--timeout 900` — 15 minutes, so a 3-minute Deep Research stream is safe
  (the default is 5 minutes; the maximum is 60).
- `--concurrency 4` — each request holds real memory; don't pack many into
  one instance.
- `--max-instances 2` — a hard ceiling on spend if the link gets traffic.
- `--allow-unauthenticated` — public demo, as intended.

**Secrets:** `--set-env-vars` puts values in the service config. For anything
longer-lived use Secret Manager instead:

```bash
echo -n "your-key" | gcloud secrets create OLLAMA_API_KEY --data-file=-
gcloud run services update stockagent --region us-central1 \
  --set-secrets "OLLAMA_API_KEY=OLLAMA_API_KEY:latest"
```

**Cap the spend:** Billing → Budgets & alerts → budget of $1 with email
alerts. With `--max-instances 2` and scale-to-zero, an idle demo costs $0.

---

## Why not Render / other 512 MB free tiers

Render's free web service is the obvious no-credit-card option, and it
**will not work here**: 512 MB RAM against a measured 498 MiB peak, plus
0.1 CPU (a ~22 s import becomes minutes) and a 15-minute idle spin-down, so
the first visitor after a quiet spell waits through a very slow cold start.

Render *would* work on a Standard instance (2 GB, ~$25/month). If you want a
no-card option more than you want a good demo, the honest answer is that this
app is too heavy for the free tiers that exist today — the lighter path would
be deploying only Terminal + Deep Research with Chat disabled, which still
doesn't fix the 0.1 CPU problem.

Other options worth knowing:

- **Azure Container Apps** — free grant similar to Cloud Run (card required),
  same container works.
- **Oracle Cloud Always Free** — a genuinely free 24 GB ARM VM, no ongoing
  cost, but you manage the VM yourself (Docker, reverse proxy, TLS) and the
  image must be built for ARM.
- **Hugging Face Spaces** — Docker Spaces now require a paid plan, so the
  free tier is no longer an option.

---

## Before you share the link

- **Your API keys pay for every visitor.** The demo is fully open: anyone with
  the URL spends your Ollama, Tavily and Google quota. Use keys created for
  this demo and rotate them when you're done.
- **Yahoo Finance often throttles datacenter IPs.** This is the most likely
  way a cloud demo fails while your laptop works fine — tools return
  human-readable errors rather than crashing, but reports may come back thin.
  If it's bad, redeploy in a different region.
- **Chat writes to your database.** Each browser gets its own generated user
  id, so visitors don't see each other's conversations, but every conversation
  still lands in your Postgres. Point `DATABASE_URL` at a throwaway database
  if you'd rather keep your own data clean.
- **Chat is optional.** Leave `DATABASE_URL` unset and the service still runs:
  `/api/health` reports `database: false`, Chat returns a clean 503, and
  Terminal and Deep Research work normally.
- **Supabase** accepts connections from anywhere by default, so the pooler URL
  works from Cloud Run with no allowlist change.

## Updating the demo

```bash
gcloud run deploy stockagent --source . --region us-central1   # redeploy
gcloud run services logs tail stockagent --region us-central1  # watch logs
```

## Local checks worth repeating before any deploy

```bash
docker build -t stockagent .
docker run --rm -p 8000:8000 --env-file .env stockagent
curl localhost:8000/api/health          # {"status":"ok","database":true}
curl -o /dev/null -w "%{http_code}\n" localhost:8000/   # 200 — UI on same origin
```

> On Windows, `docker --env-file` does **not** strip quotes around values the
> way `python-dotenv` does. If your `.env` has `DATABASE_URL="postgres..."`,
> the container receives the quotes too. The app strips surrounding quotes
> defensively, but an unquoted `.env` avoids the whole class of problem.
