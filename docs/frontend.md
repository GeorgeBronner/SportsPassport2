# Frontend

React 18 + TypeScript SPA built with Vite, styled with Tailwind CSS, served by the FastAPI backend.

## Pages
- **Login/Register** — authentication with form validation
- **Dashboard** — overview with key stats and top teams
- **Games** — browse/search games with team and season filters
- **My Games** — attended games with notes management
- **Statistics** — breakdown by teams, seasons, stadiums, states
- **Admin** — data refresh and user management (admin only)

## Key Features
- Protected routes (auth required for all pages except login/register)
- Admin-only routes with permission checking
- Responsive, mobile-friendly design (Tailwind)
- Real-time inline attendance marking (no page reload)
- User-friendly error handling and loading states
- JWT token management — auto-attach to requests, auto-redirect on expiry

## Build & Deployment
- Vite builds static assets to `backend/static/`
- FastAPI serves the frontend via `StaticFiles`
- Docker multi-stage build: frontend built in Node container, copied to Python container
- Everything served on a single port (8000)

## Development Workflow
```bash
# Dev mode with hot reload (http://localhost:5173)
cd frontend && npm run dev

# Production build (outputs to backend/static/)
cd frontend && npm run build

# Full Docker build (includes frontend)
docker compose up -d --build
```
