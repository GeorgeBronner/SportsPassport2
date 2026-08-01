# Deployment

SportsPassport2 runs as a single container (FastAPI serving the built frontend from
`backend/static/`) behind nginx-proxy-manager, on two hosts.

| | Staging | Production |
|---|---|---|
| Host | `docker31` (SSH alias) | Oracle Cloud (`oracle` SSH alias + Docker context) |
| Project path | `/home/george/docker-config/sportspassport2` | `/home/ubuntu/docker-config/sportspassport2` |
| Compose file | `docker-compose-stage.yml` | `docker-compose.yml` |
| Container | `sp2-stage-backend` | `sportspassport2-backend` |
| Port | `8003:8000` | none published — reached over the `nginx-proxy` network |
| Database | `data/sports_passport.db` | `data/sports_passport.db` |

Both hosts mount `./data` at `/app/data`. **That volume is the only persistent state** —
database, scraped logos, geocode cache, and any `raw/` bulk import files. The image
contains none of it, and the mount shadows whatever the image put at that path.

Each environment has its **own** database. Nothing is copied between them; a league
imported on one host does not appear on the other.

## Environment

Each host needs `backend/.env` (not in the repo):

```bash
DATABASE_URL=sqlite:////app/data/sports_passport.db
SECRET_KEY=<generated>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
CFB_API_KEY=<collegefootballdata.com key>   # also authenticates CBB against CBBD
CFB_API_URL=https://api.collegefootballdata.com
APP_NAME=Sports Passport
DEBUG=False                                  # True on staging only
```

Generate a `SECRET_KEY`: `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`

Optional, both default sensibly: `SCHEDULER_ENABLED` (default `true`), `SYNC_HOUR`
(default `6`, server-local), `SYNC_LOOKBACK_DAYS` (default `3`), `SENTRY_DSN`.

## Deploy

Staging:
```bash
ssh docker31 "cd docker-config/sportspassport2 && git pull origin main && \
  docker compose -f docker-compose-stage.yml up -d --build"
```

Production:
```bash
ssh oracle "cd docker-config/sportspassport2 && git pull origin main && \
  docker compose up -d --build"
```

Verify:
```bash
ssh docker31 "docker logs sp2-stage-backend --tail 20"
ssh docker31 "docker exec sp2-stage-backend curl -sf http://localhost:8000/health"

docker --context oracle logs sportspassport2-backend --tail 20
docker --context oracle exec sportspassport2-backend curl -sf http://localhost:8000/health
```

The container's command is `alembic upgrade head && uvicorn ...`, so **migrations run
automatically at start** and a failed migration means the container never serves. The
startup log should show each revision applied; check it after any deploy carrying one.

## Importing data on a host

New leagues and historical backfills do **not** arrive with a deploy — only the code
does. After deploying a new league, populate it on each host separately.

The nightly sync (06:00 server-local) creates an enabled `SyncState` for any
adapter-backed league it finds, so a newly deployed league picks up its teams and the
current season on its own overnight. History still needs an explicit import.

API-sourced seasons need nothing but the container:
```bash
# admin-authenticated POST
/api/admin/import/<LEAGUE>/historical?start_season=<Y>&end_season=<Y>
```

**Bulk-file-sourced seasons need the file copied up first.** `backend/data/raw/` is
gitignored, so bulk files are never in the image or the repo — a fresh host has none.
Copy into the host's data volume, which the container sees at `/app/data/raw/`:

```bash
scp backend/data/raw/mls/matches.csv \
  docker31:/home/george/docker-config/sportspassport2/data/raw/mls/matches.csv
```

Adapters that need a missing bulk file raise with download instructions rather than a
bare `FileNotFoundError`. Which seasons need one is per-league — for MLS, only before
2013 (see `services/adapters/mls.py`); 2013+ comes from the ASA API.

Take a WAL-safe backup before any import that writes at scale, and verify against it
afterwards:
```bash
docker exec <container> python -c "
import sqlite3
src=sqlite3.connect('/app/data/sports_passport.db')
dst=sqlite3.connect('/app/data/sports_passport.pre-<change>.db')
src.backup(dst)"
```
`.backup` rather than `cp` — the database runs in WAL mode, so a file copy can catch it
mid-checkpoint. Delete superseded backups once the change is verified; they are ~145 MB
each.

## Network

Both containers join the external `nginx-proxy` network:

```yaml
services:
  backend:
    networks: [nginx-proxy]
networks:
  nginx-proxy:
    external: true
```

```bash
docker --context oracle inspect sportspassport2-backend \
  --format '{{range $net, $c := .NetworkSettings.Networks}}{{$net}} {{end}}'
docker --context oracle network inspect nginx-proxy \
  --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}} {{end}}'
```

## Common commands

```bash
# staging (SSH only — no local Docker context)
ssh docker31 "docker logs sp2-stage-backend --tail 50 -f"
ssh docker31 "cd docker-config/sportspassport2 && docker compose -f docker-compose-stage.yml restart"
ssh docker31 "docker exec -it sp2-stage-backend sh"

# production (Docker context available locally)
docker --context oracle logs sportspassport2-backend --tail 50 -f
docker --context oracle exec -it sportspassport2-backend sh
docker --context oracle inspect sportspassport2-backend --format '{{.State.Health.Status}}'
ssh oracle "cd docker-config/sportspassport2 && docker compose restart"
```

## Troubleshooting

**Container won't start** — check logs first. Because the command chains
`alembic upgrade head && uvicorn`, a migration failure looks like a container that exits
before ever logging a startup line. Other causes: missing/invalid `.env`, port conflict.

**A league is empty after deploying it** — expected. Code deploys; data does not. See
"Importing data on a host".

**An import fails on a missing file** — the bulk file is gitignored and has to be copied
to that host's `data/raw/` directory.

**Not reachable through nginx-proxy-manager** — confirm the container is on the
`nginx-proxy` network, then test internally:
`docker exec <container> curl -sf http://localhost:8000/health`.

**After a deploy** — frontend and Python dependency changes need `--build`; config-only
changes need just a restart; schema changes apply themselves via Alembic.
