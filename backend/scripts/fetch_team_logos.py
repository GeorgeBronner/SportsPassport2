"""One-time/occasional team logo scrape from ESPN's public team-list API.

For each league, pulls ESPN's team list (which includes CDN logo URLs), matches
teams to our DB rows by normalized name, downloads each matched logo to
data/logos/<league>/<team_id>.png, and sets teams.logo_url.

Only active teams (last_season IS NULL) are matched — historical/relocated
identities (Montreal Expos, California Angels, ...) keep logo_url NULL and fall
back to the monogram badge in the UI. Idempotent: re-running skips files that
already exist (use --force to re-download) and re-points logo_url either way.

Usage (from backend/):
    uv run python scripts/fetch_team_logos.py            # all leagues
    uv run python scripts/fetch_team_logos.py --league CFB
    uv run python scripts/fetch_team_logos.py --dry-run  # match report only
"""

import argparse
import sys
import time
import unicodedata
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports_passport.db.database import SessionLocal  # noqa: E402
from sports_passport.models import League, Team  # noqa: E402

API_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# league code -> list of ESPN team-list endpoints (CFB needs FBS + FCS groups)
ESPN_ENDPOINTS = {
    "CFB": [
        f"{API_BASE}/football/college-football/teams?groups=80&limit=1000",
        f"{API_BASE}/football/college-football/teams?groups=81&limit=1000",
    ],
    "CBB": [f"{API_BASE}/basketball/mens-college-basketball/teams?groups=50&limit=1000"],
    "MLB": [f"{API_BASE}/baseball/mlb/teams"],
    "NFL": [f"{API_BASE}/football/nfl/teams"],
    "NBA": [f"{API_BASE}/basketball/nba/teams"],
    "NHL": [f"{API_BASE}/hockey/nhl/teams"],
}

COLLEGE = {"CFB", "CBB"}

# Manual name fixups: our name -> ESPN normalized key, per league.
ALIASES = {
    "CFB": {},
    "CBB": {},
    "MLB": {"Sacramento Athletics": "Athletics"},
    "NFL": {},
    "NBA": {},
    "NHL": {"Utah Hockey Club": "Utah Mammoth"},  # franchise rebranded in 2025
}

LOGOS_DIR = Path(__file__).resolve().parent.parent / "data" / "logos"
HEADERS = {
    "User-Agent": "SportsPassport/0.2 (personal game-attendance tracker; one-time logo fetch)"
}
THROTTLE_SECONDS = 0.15


def norm(s: str) -> str:
    """Normalize a name for matching: strip accents, lowercase, alnum only."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", "and")
    return "".join(c for c in s if c.isalnum())


def pick_logo(logos: list) -> str | None:
    """Prefer the plain 'default' logo over dark/scoreboard variants."""
    for logo in logos or []:
        if "default" in (logo.get("rel") or []):
            return logo.get("href")
    return (logos or [{}])[0].get("href")


def fetch_espn_teams(client: httpx.Client, league_code: str) -> dict[str, dict]:
    """Return {normalized_key: {'id', 'display', 'logo'}} for one league.

    College teams are keyed by location ('Alabama'); pros by displayName
    ('Atlanta Falcons'). Both also get a displayName key as fallback.
    """
    lookup: dict[str, dict] = {}
    for url in ESPN_ENDPOINTS[league_code]:
        resp = client.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        teams = data["sports"][0]["leagues"][0]["teams"]
        for entry in teams:
            t = entry["team"]
            logo = pick_logo(t.get("logos"))
            if not logo:
                continue
            info = {"id": t["id"], "display": t.get("displayName", ""), "logo": logo}
            keys = [norm(t.get("displayName", ""))]
            if league_code in COLLEGE:
                keys.append(norm(t.get("location", "")))
            for key in keys:
                if key:
                    # first writer wins; ESPN duplicates are rare and identical
                    lookup.setdefault(key, info)
        time.sleep(THROTTLE_SECONDS)
    return lookup


def match_key_candidates(team: Team, league_code: str) -> list[str]:
    """Normalized keys to try for a DB team, most specific first."""
    keys = []
    alias = ALIASES[league_code].get(team.name)
    if alias:
        keys.append(norm(alias))
    if league_code in COLLEGE:
        keys.append(norm(team.name))  # college name is the school/location
        if team.nickname:
            keys.append(norm(f"{team.name} {team.nickname}"))  # displayName form
    else:
        keys.append(norm(team.name))  # pro name is the full displayName
    return [k for k in keys if k]


def process_league(client: httpx.Client, db, league: League, force: bool, dry_run: bool):
    espn = fetch_espn_teams(client, league.code)
    active = (
        db.query(Team)
        .filter(Team.league_id == league.id, Team.last_season.is_(None))
        .all()
    )

    out_dir = LOGOS_DIR / league.code.lower()
    matched, downloaded, unmatched = 0, 0, []

    for team in active:
        info = None
        for key in match_key_candidates(team, league.code):
            info = espn.get(key)
            if info:
                break
        if not info:
            unmatched.append(team.name)
            continue

        matched += 1
        if dry_run:
            continue

        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{team.id}.png"
        if force or not dest.exists():
            resp = client.get(info["logo"], headers=HEADERS, timeout=30)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            downloaded += 1
            time.sleep(THROTTLE_SECONDS)
        team.logo_url = f"/logos/{league.code.lower()}/{team.id}.png"

    if not dry_run:
        db.commit()

    print(
        f"{league.code}: ESPN teams {len(espn)} keys · DB active {len(active)} · "
        f"matched {matched} · downloaded {downloaded} · unmatched {len(unmatched)}"
    )
    # College leagues legitimately have hundreds of unmatched small schools;
    # for pro leagues every active team should match, so list the misses.
    if unmatched and (league.code not in COLLEGE or len(unmatched) <= 15):
        print(f"  unmatched: {', '.join(sorted(unmatched))}")
    return unmatched


def main():
    parser = argparse.ArgumentParser(description="Fetch team logos from ESPN")
    parser.add_argument("--league", choices=sorted(ESPN_ENDPOINTS), help="single league code")
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    parser.add_argument("--dry-run", action="store_true", help="report matches without downloading")
    args = parser.parse_args()

    codes = [args.league] if args.league else list(ESPN_ENDPOINTS)
    with SessionLocal() as db, httpx.Client(follow_redirects=True) as client:
        for code in codes:
            league = db.query(League).filter(League.code == code).first()
            if not league:
                print(f"{code}: league not found in DB, skipping")
                continue
            process_league(client, db, league, args.force, args.dry_run)


if __name__ == "__main__":
    main()
