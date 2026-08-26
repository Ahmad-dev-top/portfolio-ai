# My Portfolio Website

Everything for Muhammad Ahmad's portfolio: the site itself, and the Python service behind
Dogar and the private content studio.

```
My Portfolio Website/
├── portfolio.html          the whole website — one file, opens in any browser
├── START-HERE.md           this file
└── dogar-api/              the backend (Dogar + admin studio)
    ├── app/                FastAPI application
    │   ├── main.py         routes, CORS, rate limits, Groq call
    │   ├── auth.py         passphrase hashing, session tokens
    │   ├── rag.py          local embeddings, chunking, cosine search
    │   ├── store.py        SQLite content + vector index
    │   └── config.py       reads .env — the only place secrets load
    ├── .env.example        copy to .env, fill in, never commit
    ├── requirements.txt    Python dependencies
    ├── Dockerfile          container build
    ├── docker-compose.yml  API + Caddy (automatic HTTPS)
    ├── Caddyfile           reverse proxy config — put your domain here
    ├── keepalive.sh        stops Oracle reclaiming an idle instance
    ├── README.md           setup, architecture, security checklist
    └── DEPLOY-ORACLE.md    step-by-step Oracle Cloud deployment
```

## Using the site right now

Double-click `portfolio.html`. It works offline — your photo is embedded, and Dogar answers
from an index built out of the page's own content. No installation, no server.

**The private studio:** press `Ctrl+Shift+E`, or add `#studio` to the URL. Five tabs for
editing identity, accounts, projects, timeline, and Dogar's knowledge. Changes apply live.
"Export JSON" saves your content to a file.

Until the backend is deployed, studio edits last only until you refresh, and the studio is
*hidden* rather than *secure* — anyone reading the page source could find it. That changes
once the API is connected.

## When you're ready for the real thing

1. **Rotate your Groq key.** The one shared in chat should be deleted at console.groq.com and
   replaced. The new one goes in `.env` only.
2. Read `dogar-api/README.md` for local setup.
3. Read `dogar-api/DEPLOY-ORACLE.md` to put it on your Always Free VM.
4. Set the two endpoints at the top of `portfolio.html`:

```js
agent: { endpoint: "https://api.your-domain.com/api/chat", ... }
admin: { endpoint: "https://api.your-domain.com/api/admin" }
```

Dogar's badge switches to `groq · rag`, the studio gets a real sign-in gate, and edits save
server-side for every visitor.

## Editing content without the studio

Open `portfolio.html` in any editor and find `const CONFIG = {` — around line 850. Everything
the site displays lives there: identity, social links, projects, timeline, Dogar's knowledge.
Anything left as `null` renders as an orange "pending" marker rather than invented filler.

## Still unfinished

- **Social links** — every URL is `null`, so the "Find me online" section shows a placeholder.
- **Projects** — the array is empty; the section shows a "coming soon" card until you add one.
- **Employer / role** for the 2024 → Present timeline entry.
- **Contact form delivery** — `contactService` is `null`, so the form validates but sends
  nothing. Formspree, Resend, EmailJS or an n8n webhook can be wired in.

## Two things worth remembering

**Frontend code can never be hidden.** Every browser downloads `portfolio.html` to render it.
That's fine — nothing sensitive lives there. Your Groq key, passphrase and Dogar's knowledge
are all server-side.

**Never paste an API key into a chat, email or screenshot.** If it happens, rotate the key
immediately. Secrets belong in `.env` and in your host's environment panel — nowhere else.
