# Deploying Dogar on Oracle Cloud Always Free

A real VM with a real disk — no sleep timer, no ephemeral filesystem, no monthly bill.
Two Oracle-specific traps to avoid, both covered below.

## 1. Create the instance

Console → Compute → Instances → Create.

- **Shape:** `VM.Ampere.A1.Flex` — **2 OCPU / 12 GB** (the Always Free ceiling since
  15 June 2026; the old 4/24 allocation was halved)
- **Image:** Ubuntu 24.04 (ARM build — the A1 shapes are aarch64)
- **SSH key:** upload yours, or let Oracle generate one and download it

If you hit **"Out of capacity"**, that's normal for A1 in busy regions. Retry at a
different hour, or pick a different availability domain. It usually clears.

## 2. Open the ports — both firewalls

This is where most Oracle deployments stall. There are **two** firewalls, and Oracle's
Ubuntu image ships with iptables rules that block everything but SSH.

**a) Security List** (Console → Networking → VCN → Subnet → Security List → Add Ingress):

| Source | Protocol | Port |
|---|---|---|
| 0.0.0.0/0 | TCP | 80 |
| 0.0.0.0/0 | TCP | 443 |

**b) On the VM itself:**

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

Skip step (b) and your site will be unreachable while everything looks correctly configured.

## 3. Install Docker

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git
sudo usermod -aG docker $USER && newgrp docker
```

## 4. Deploy

```bash
git clone <your-private-repo> dogar-api && cd dogar-api
cp .env.example .env
nano .env          # new Groq key, ADMIN_SECRET, ADMIN_PASS_HASH, ALLOWED_ORIGINS
```

Generate the two secrets first:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
docker run --rm -v $PWD:/w -w /w python:3.12-slim sh -c "pip install -q PyJWT && python -m app.auth 'your passphrase'"
```

Point the `Caddyfile` at your domain, add an A record for it pointing at the VM's public IP,
then:

```bash
docker compose up -d --build
```

The first build takes 5–10 minutes on ARM — it downloads the embedding model into the image
so the first visitor never waits.

Verify: `curl https://api.your-domain.com/api/health`

## 5. Stop Oracle reclaiming your instance

Oracle deems an Always Free instance idle if, across a 7-day window, CPU sits below 20% at
the 95th percentile — and reclaims it. A portfolio API idles near 0%, so this will eventually
happen unless you prevent it.

```bash
crontab -e
```

Add:

```
*/20 * * * * /home/ubuntu/dogar-api/keepalive.sh
```

`keepalive.sh` pings the health endpoint and burns ~45 seconds of CPU every 20 minutes —
enough to stay clear of the threshold.

**The more reliable fix:** upgrade the account to Pay As You Go. It stays free within the
Always Free limits, and idle reclamation no longer applies. You need a card on file, and
you should set a **budget alert at $1** so any accidental overage is caught immediately.

## 6. Point the site at it

In `portfolio.html`:

```js
agent: { endpoint: "https://api.your-domain.com/api/chat", ... }
admin: { endpoint: "https://api.your-domain.com/api/admin" }
```

Set `ALLOWED_ORIGINS` in `.env` to wherever the portfolio is hosted, then
`docker compose restart api`.

## Oracle-specific gotchas, in one place

| Symptom | Cause |
|---|---|
| "Out of capacity" on create | A1 demand in your region. Retry later or change AD. |
| Site unreachable, config looks right | You skipped the iptables step. |
| Instance vanished after a week | Idle reclamation. Install the cron job. |
| Instance shut down unexpectedly | You're above 2 OCPU / 12 GB. Edit the shape down. |
| `pip` fails building a wheel | ARM. Build inside Docker, as above — don't install on the host. |

## Backups

Your content lives in `./data/portfolio.db`. Back it up:

```bash
0 3 * * * cp /home/ubuntu/dogar-api/data/portfolio.db /home/ubuntu/backup-$(date +\%u).db
```

Seven rotating daily copies. Oracle's Always Free block storage is 200 GB — plenty.
