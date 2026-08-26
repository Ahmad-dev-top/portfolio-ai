# Dogar — Python backend

FastAPI service holding everything that must stay private: the Groq key, your admin
passphrase, the content database, and Dogar's retrieval index.

## What is actually private, and what is not

| Thing | Visible to visitors? |
|---|---|
| This Python code | **No.** It runs on your server. Browsers receive JSON, never source. |
| Groq API key | **No.** Read from `.env` on the server, sent only server→Groq. |
| Admin passphrase | **No.** Only a PBKDF2 hash exists, and only in `.env`. |
| Dogar's knowledge passages | **No.** Stripped from every public response. |
| `portfolio.html` and its JavaScript | **Yes — unavoidably.** Every browser must download it to render the page. |

That last row is the reason this backend exists. Nothing sensitive lives in the frontend
anymore, so it being readable stops mattering. Minifying it would only make it tedious to
read, not private — don't mistake that for security.

## First: rotate your key

The key you pasted into a chat should be considered burned. Delete it at
console.groq.com, create a new one, and put the new one in `.env` only.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Generate the two secrets:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # → ADMIN_SECRET
python -m app.auth "the passphrase you want to use"            # → ADMIN_PASS_HASH
```

Paste both into `.env`, add your new Groq key, then:

```bash
uvicorn app.main:app --reload
```

Check it: `curl http://localhost:8000/api/health`

## Connect the site

In `portfolio.html`:

```js
agent: { endpoint: "https://your-api.com/api/chat", ... }
admin: { endpoint: "https://your-api.com/api/admin" }
```

Dogar's badge changes to `groq · rag`, and the Studio shows a real sign-in gate.

## Deploy

Any host that runs a container works — Railway, Render, Fly.io, or a VPS. The `Dockerfile`
is ready and pre-warms the embedding model so the first question isn't slow.

Set the `.env` values in the host's environment-variables panel. Never commit `.env`;
it's already in `.gitignore`. Keep the repository private.

## How it fits together

```
Visitor asks a question
   → POST /api/chat
   → embed the question locally (fastembed, no external call)
   → cosine-rank stored passages, keep the top 4 above 0.30
   → nothing above the floor?  →  "I don't have that on file"
   → else send passages + question to Groq with a strict no-invention prompt
   → return the answer plus which passage it came from
```

Embeddings run locally rather than through a second paid API. The model is ~130MB, CPU-only,
and your content never leaves your server during retrieval.

## Files

| File | Does |
|---|---|
| `app/main.py` | Routes, CORS lock, rate limits, Groq call |
| `app/auth.py` | PBKDF2 passphrase hashing, JWT session tokens |
| `app/rag.py` | Local embeddings, chunking, cosine search |
| `app/store.py` | SQLite content + vector storage |
| `app/config.py` | Reads `.env`, the only place secrets are loaded |

## Security checklist before going live

- [ ] Old Groq key deleted at console.groq.com
- [ ] `.env` is not in git (`git check-ignore .env` prints the filename)
- [ ] Repository is private
- [ ] `ALLOWED_ORIGINS` names your domain only — no `*`
- [ ] A wrong passphrase returns 401 (test it)
- [ ] `PUT /api/admin/content` without a token returns 401 (test it)
- [ ] HTTPS is on — a token over plain HTTP is a token anyone on the network can copy
- [ ] Rate limits confirmed: 15 chats/minute per IP, 5 login attempts/minute

## Swapping SQLite for PostgreSQL

If you'd rather run Neon with `pgvector` — the stack you already use — only the four
functions in `app/store.py` change. Nothing else touches the database.

## Running 24/7

Three things decide whether Dogar is actually reachable at 3am:

### 1. A host that doesn't sleep

Free tiers idle your app after inactivity, so the first visitor after a quiet spell waits
30–60 seconds — or sees nothing.

| Host | Always on? | Cost |
|---|---|---|
| Render free | No — sleeps after 15 min idle | Free |
| Render Starter | Yes | ~$7/mo |
| Railway | Yes | ~$5/mo usage-based |
| Fly.io | Yes, if `min_machines_running = 1` | ~$3–5/mo |
| VPS (Hetzner, Contabo) | Yes | ~$4–5/mo |

Needs at least **512MB RAM** — the embedding model wants ~200MB resident.

A keep-alive ping (UptimeRobot, every 5 min, hitting `/api/health`) papers over sleepy free
tiers, but the cold start still bites after a redeploy. Paying a few dollars is the honest fix.

### 2. Storage that survives restarts

SQLite writes to disk, and container filesystems are wiped on every redeploy. Without a
persistent volume your content silently resets to empty.

- **Railway** — add a Volume, mount at `/srv/data`
- **Fly.io** — `fly volumes create dogar_data`, mount at `/srv/data`
- **Render** — add a Disk (paid plans only)
- **Or** switch `app/store.py` to PostgreSQL on Neon — free tier, no volume needed

Set `DB_PATH=/srv/data/portfolio.db` to point at the mounted volume.

### 3. Groq quota

The free tier has daily token limits. When they run out — or if Groq has an outage — the
service now **degrades instead of failing**: it returns the retrieved passage directly, marked
`degraded: true`. The answer is less conversational but still accurate and still from your
content. Visitors get something useful either way.

Watch usage at console.groq.com. If the portfolio gets real traffic, the paid tier removes
the ceiling.

### Monitoring

Point UptimeRobot or Better Stack at `/api/health`. It returns `{"ok": true, "passages": N}` —
if `passages` drops to 0, your volume didn't mount and the index is gone.
