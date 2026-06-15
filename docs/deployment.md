# Production Deployment

The app deploys to an Oracle Cloud server via Docker Compose, behind nginx-proxy-manager.

## Oracle Server Configuration
- **Server**: Oracle Cloud Ubuntu instance
- **Access**: SSH via `oracle` alias
- **Docker Context**: `oracle`
- **Project Path**: `/home/ubuntu/SportsPassport2`
- **Port**: 8001 (mapped to container's 8000)
- **Network**: `nginx-proxy` (shared with nginx-proxy-manager)

## Environment Setup
The production server requires `backend/.env`:
```bash
# Database
DATABASE_URL=sqlite:////app/data/college_football.db

# Security (generate unique SECRET_KEY for production)
SECRET_KEY=<generated-secret-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CollegeFootballData.com API
CFB_API_KEY=<api-key>
CFB_API_URL=https://api.collegefootballdata.com

# Application
APP_NAME=College Football Game Tracker
DEBUG=False
```

Generate a `SECRET_KEY`:
```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

## Deployment Workflow

**Prerequisites:** all changes committed/pushed to `main`; Docker context `oracle` accessible.

**One-line deployment (no `.env` changes):**
```bash
git push origin main && ssh oracle "cd SportsPassport2 && git pull origin main && docker compose up -d --build"
```

**Step by step:**
1. Commit and push locally: `git add . && git commit -m "..." && git push origin main`
2. Pull on Oracle: `ssh oracle "cd SportsPassport2 && git pull origin main"`
3. Rebuild/restart: `ssh oracle "cd SportsPassport2 && docker compose up -d --build"`
4. Verify:
   ```bash
   docker --context oracle ps | grep cfb-tracker
   docker --context oracle logs cfb-tracker-backend --tail 20
   docker --context oracle exec cfb-tracker-backend curl -f http://localhost:8000/health
   ```

## Network Configuration
The container must be on the external `nginx-proxy` network to be reachable through nginx-proxy-manager:
```yaml
# docker-compose.yml
services:
  backend:
    networks:
      - nginx-proxy

networks:
  nginx-proxy:
    external: true
```

Verify:
```bash
# Which network the container is on
docker --context oracle inspect cfb-tracker-backend --format '{{range $net, $config := .NetworkSettings.Networks}}{{$net}}{{end}}'

# All containers on nginx-proxy network
docker --context oracle network inspect nginx-proxy --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}} {{end}}'
```

## Common Production Commands
```bash
docker --context oracle logs cfb-tracker-backend --tail 50 -f      # view logs
ssh oracle "cd SportsPassport2 && docker compose restart"          # restart, no rebuild
ssh oracle "cd SportsPassport2 && docker compose down"             # stop
docker --context oracle exec cfb-tracker-backend <command>         # run command
docker --context oracle exec -it cfb-tracker-backend sh            # shell
docker --context oracle inspect cfb-tracker-backend --format '{{.State.Health.Status}}'  # health
docker --context oracle ps                                         # running containers
```

## Troubleshooting

**Container won't start:**
1. Check logs: `docker --context oracle logs cfb-tracker-backend`
2. Common causes: missing/invalid `.env`, database connection problems, port conflicts

**Network connectivity issues:**
1. Verify container is on the nginx-proxy network
2. Check nginx-proxy-manager configuration
3. Test internal connectivity: `docker --context oracle exec cfb-tracker-backend curl http://localhost:8000/health`

**After deployment changes:**
- Frontend changes require rebuild (included in `--build`)
- Python dependency changes require rebuild
- Configuration changes may only need restart
- Database schema changes run automatically via Alembic migrations
