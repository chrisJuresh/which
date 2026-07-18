# Deployment

`https://which.chrisj.uk` is served from the home server by a small Docker
Compose stack, exposed through a Cloudflare Tunnel (no open inbound ports, home
IP hidden, TLS at Cloudflare's edge).

## Pieces

- **web** — Caddy serving the built SvelteKit SPA (baked into the image) plus the
  archive data + captures, bind-mounted from the host:
  - `/srv/which/data` → `/site/data` (archive.json)
  - `/srv/which/captures` → `/site/captures` (rewritten raw-HTML pages)
- **cloudflared** — runs the `which` Cloudflare Tunnel; ingress
  `which.chrisj.uk` → `http://web:80`.
- **watchtower** — auto-pulls new images CI pushes to GHCR. Scoped to `which`
  only, so it never touches the rest of the homelab.

## CI/CD

`.github/workflows/deploy.yml` builds `deploy/Dockerfile` and pushes
`ghcr.io/chrisjuresh/which:latest` on every push to `main` (using the built-in
`GITHUB_TOKEN` — no secrets to configure). Watchtower on the server pulls it
within ~2 min. Rollback = re-run an older workflow or `docker compose pull` a
pinned tag.

## First-time / manual deploy

```bash
cd ~/which/deploy
cp .env.example .env          # then paste the Cloudflare Tunnel token
docker compose build web      # or let CI publish the image
docker compose up -d
```

## Updating the archive data (after a new scrape, run locally)

**PowerShell (recommended on Windows):**

```powershell
./scripts/sync-data.ps1        # re-exports, then uploads captures + archive.json
```

Do **not** use `tar czf - | ssh` in PowerShell — PowerShell re-encodes the binary
pipe and corrupts it (`gzip: stdin: not in gzip format`). The script packs a
temp tarball and copies it with `scp` instead. In a real POSIX shell (Git Bash /
WSL) the streamed pipe is fine:

```bash
uv run python export_archive_data.py
tar czf - -C archive-web/static/captures raw-html | \
  ssh -p 22222 chris@<server> 'tar xzf - -C /srv/which/captures'
scp -P 22222 archive-web/static/data/archive.json chris@<server>:/srv/which/data/
```

The site picks up new data immediately (bind-mounted, read at request time).
