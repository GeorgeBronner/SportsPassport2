"""One-off backfill: apply the NFL/NHL/NBA venue seeds (sports_passport/data/seed/*.csv) onto
an already-populated database, without re-running the (slow, network-bound)
adapters. Fixes the gaps those seeds were built for:

- NFL: existing venues (keyed by nflverse's stadium_id, unchanged by the seed)
  get city/state/country/lat/lon filled in.
- NBA: games whose venue_id is NULL (Games.csv only carries arena data for its
  current season) get linked to a seed-derived venue where the team+season
  falls in the seed's 1990-present coverage.
- NHL: every game gets re-resolved onto the seed's team+season-keyed venue
  (sports_passport/data/seed/nhl_arenas.csv), replacing the old name-keyed venue link — this
  is what makes future naming-rights renames non-breaking (see nhl.py). Old
  name-keyed venue rows are left in place (harmless, just unreferenced) once
  their games are repointed.

Safe to re-run: matching is idempotent (upsert_venue dedups by source +
source_venue_id) and rows already at their seed-correct venue are skipped.

Usage (from backend/):
    uv run python scripts/backfill_venue_seeds.py            # all three leagues
    uv run python scripts/backfill_venue_seeds.py --league NHL
    uv run python scripts/backfill_venue_seeds.py --dry-run
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sports_passport.db.database import SessionLocal  # noqa: E402
from sports_passport.models import Game, League, Team, Venue  # noqa: E402
from sports_passport.services.adapters import venue_seed  # noqa: E402
from sports_passport.services.importer import upsert_venue  # noqa: E402


def backfill_nfl(db, dry_run: bool) -> int:
    venues = db.query(Venue).filter(Venue.source == "nflverse").all()
    changed = 0
    for v in venues:
        seed = venue_seed.nfl_stadiums().get(v.source_venue_id)
        if not seed:
            continue
        fields = venue_seed.venue_fields(seed)
        if v.latitude == fields["latitude"] and v.city == fields["city"]:
            continue  # already up to date (re-run safety)
        changed += 1
        if not dry_run:
            for key, value in fields.items():
                if value is not None:
                    setattr(v, key, value)
    if not dry_run and changed:
        db.commit()
    return changed


def backfill_nba(db, dry_run: bool) -> int:
    league = db.query(League).filter(League.code == "NBA").first()
    if not league:
        return 0
    rows = (
        db.query(Game.id, Game.season, Team.franchise_id)
        .join(Team, Game.home_team_id == Team.id)
        .filter(Game.league_id == league.id, Game.venue_id.is_(None))
        .all()
    )
    venue_cache: dict[str, int] = {}
    updates = []
    for game_id, season, franchise_id in rows:
        if franchise_id is None:
            continue
        seed = venue_seed.lookup_nba_arena(franchise_id, season)
        if not seed:
            continue
        cache_key = seed["arena"]
        venue_id = venue_cache.get(cache_key)
        if venue_id is None:
            if dry_run:
                venue_id = -1
            else:
                venue, _ = upsert_venue(
                    db, source="nba-kaggle", source_venue_id=f"seed-{seed['arena']}",
                    name=seed["arena"], **venue_seed.venue_fields(seed),
                )
                db.flush()
                venue_id = venue.id
            venue_cache[cache_key] = venue_id
        updates.append({"id": game_id, "venue_id": venue_id})
    if not dry_run and updates:
        db.bulk_update_mappings(Game, updates)
        db.commit()
    return len(updates)


def backfill_nhl(db, dry_run: bool) -> int:
    league = db.query(League).filter(League.code == "NHL").first()
    if not league:
        return 0
    rows = (
        db.query(Game.id, Game.season, Team.abbreviation, Game.venue_id)
        .join(Team, Game.home_team_id == Team.id)
        .filter(Game.league_id == league.id)
        .all()
    )
    venue_cache: dict[tuple, int] = {}
    updates = []
    for game_id, season, tricode, old_venue_id in rows:
        if not tricode:
            continue
        seed = venue_seed.lookup_nhl_arena(tricode, season)
        if not seed:
            continue
        cache_key = (seed["tricode"], seed["start_season"])
        venue_id = venue_cache.get(cache_key)
        if venue_id is None:
            if dry_run:
                venue_id = -1
            else:
                venue, _ = upsert_venue(
                    db, source="nhl", source_venue_id=f"nhl-{seed['tricode']}-{seed['start_season']}",
                    name=seed["arena"], **venue_seed.venue_fields(seed),
                )
                db.flush()
                venue_id = venue.id
            venue_cache[cache_key] = venue_id
        if old_venue_id != venue_id:
            updates.append({"id": game_id, "venue_id": venue_id})
    if not dry_run and updates:
        db.bulk_update_mappings(Game, updates)
        db.commit()
    return len(updates)


BACKFILLS = {"NFL": backfill_nfl, "NBA": backfill_nba, "NHL": backfill_nhl}


def main():
    parser = argparse.ArgumentParser(description="Backfill NFL/NHL/NBA venue seeds onto existing data")
    parser.add_argument("--league", choices=sorted(BACKFILLS), help="single league code")
    parser.add_argument("--dry-run", action="store_true", help="report counts without writing")
    args = parser.parse_args()

    codes = [args.league] if args.league else list(BACKFILLS)
    with SessionLocal() as db:
        for code in codes:
            count = BACKFILLS[code](db, args.dry_run)
            verb = "would update" if args.dry_run else "updated"
            print(f"{code}: {verb} {count} row(s)")


if __name__ == "__main__":
    main()
