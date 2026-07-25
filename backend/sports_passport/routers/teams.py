from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional
from sports_passport.core.queries import LIKE_ESCAPE, contains_pattern
from sports_passport.db.database import get_db
from sports_passport.models.team import Team
from sports_passport.models.league import League
from sports_passport.models.game import Game
from sports_passport.models.attendance import UserGameAttendance
from sports_passport.schemas.team import (
    TeamResponse,
    TeamSearchResult,
    TeamAttendanceStats,
    TeamVenueCount,
)
from sports_passport.core.dependencies import get_current_user
from sports_passport.models.user import User

router = APIRouter(prefix="/api/teams", tags=["teams"])


def _attended_counts(db: Session, user_id: int, team_ids: list[int]) -> Counter:
    """Games the user attended involving each team, as {team_id: count}."""
    counts = Counter()
    if not team_ids:
        return counts
    for side in (Game.home_team_id, Game.away_team_id):
        rows = (
            db.query(side, func.count(UserGameAttendance.id))
            .join(UserGameAttendance, UserGameAttendance.game_id == Game.id)
            .filter(UserGameAttendance.user_id == user_id, side.in_(team_ids))
            .group_by(side)
            .all()
        )
        for team_id, count in rows:
            counts[team_id] += count
    return counts


@router.get("/", response_model=List[TeamResponse])
def list_teams(
    league: Optional[str] = None,
    conference: Optional[str] = None,
    search: Optional[str] = None,
    classification: Optional[str] = None,
    franchise_id: Optional[int] = None,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all teams with optional filters"""
    query = db.query(Team)

    if league:
        league_row = db.query(League).filter(League.code == league.upper()).first()
        if not league_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown league: {league}"
            )
        query = query.filter(Team.league_id == league_row.id)

    # CFB-specific fbs/fcs filter; pass 'all' or omit for everything
    if classification and classification.lower() != "all":
        query = query.filter(
            Team.classification.ilike(contains_pattern(classification), escape=LIKE_ESCAPE)
        )

    if conference:
        query = query.filter(
            Team.conference.ilike(contains_pattern(conference), escape=LIKE_ESCAPE)
        )

    if search:
        query = query.filter(Team.name.ilike(contains_pattern(search), escape=LIKE_ESCAPE))

    if franchise_id is not None:
        query = query.filter(Team.franchise_id == franchise_id)

    if active_only:
        query = query.filter(Team.last_season.is_(None))

    teams = query.order_by(Team.name).offset(skip).limit(limit).all()
    return teams


@router.get("/search", response_model=List[TeamSearchResult])
def search_teams(
    q: str = Query(..., min_length=2),
    league: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cross-league team search for the omnibox.

    Matches name/nickname/city, returns the caller's attended count per team,
    and ranks: attended first, then prefix matches, active teams, name.
    """
    like = contains_pattern(q)
    query = (
        db.query(Team, League.code)
        .join(League, Team.league_id == League.id)
        .filter(or_(
            Team.name.ilike(like, escape=LIKE_ESCAPE),
            Team.nickname.ilike(like, escape=LIKE_ESCAPE),
            Team.city.ilike(like, escape=LIKE_ESCAPE),
        ))
    )
    if league:
        query = query.filter(League.code == league.upper())

    # Pull a generous candidate pool, rank with attendance counts, then cut.
    pool_cap = 300
    candidates = query.order_by(Team.last_season.isnot(None), Team.name).limit(pool_cap).all()
    if len(candidates) == pool_cap:
        # The pool hit the cap, so a matching attended team may have been
        # truncated — merge them in; attendance-first ranking must never
        # lose a team to the cap.
        candidate_ids = {t.id for t, _ in candidates}
        attended_matches = (
            query.join(Game, or_(
                Game.home_team_id == Team.id,
                Game.away_team_id == Team.id,
            ))
            .join(UserGameAttendance, and_(
                UserGameAttendance.game_id == Game.id,
                UserGameAttendance.user_id == current_user.id,
            ))
            .distinct()
            .all()
        )
        candidates += [row for row in attended_matches if row[0].id not in candidate_ids]
    counts = _attended_counts(db, current_user.id, [t.id for t, _ in candidates])

    q_lower = q.lower()
    ranked = sorted(
        candidates,
        key=lambda row: (
            -counts[row[0].id],
            not row[0].name.lower().startswith(q_lower),
            row[0].last_season is not None,
            row[0].name,
        ),
    )[:limit]

    return [
        TeamSearchResult(
            **TeamResponse.model_validate(team).model_dump(),
            league_code=code,
            attended_count=counts[team.id],
        )
        for team, code in ranked
    ]


@router.get("/{team_id}/attendance-stats", response_model=TeamAttendanceStats)
def team_attendance_stats(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """The caller's history with one team: record when attending, seasons, venues."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )

    games = (
        db.query(Game)
        .join(UserGameAttendance, and_(
            UserGameAttendance.game_id == Game.id,
            UserGameAttendance.user_id == current_user.id,
        ))
        .filter(or_(Game.home_team_id == team_id, Game.away_team_id == team_id))
        .order_by(Game.start_date)
        .all()
    )

    wins = losses = ties = 0
    seasons = Counter()
    venue_counts = Counter()
    venue_info = {}
    for game in games:
        seasons[game.season] += 1
        if game.home_score is not None and game.away_score is not None:
            team_score, opp_score = (
                (game.home_score, game.away_score)
                if game.home_team_id == team_id
                else (game.away_score, game.home_score)
            )
            if team_score > opp_score:
                wins += 1
            elif team_score < opp_score:
                losses += 1
            else:
                ties += 1
        if game.venue:
            venue_counts[game.venue.id] += 1
            venue_info[game.venue.id] = game.venue

    return TeamAttendanceStats(
        team_id=team_id,
        games_attended=len(games),
        wins=wins,
        losses=losses,
        ties=ties,
        games_by_season=dict(sorted(seasons.items())),
        venues=[
            TeamVenueCount(
                name=venue_info[vid].name,
                city=venue_info[vid].city,
                state=venue_info[vid].state,
                count=count,
            )
            for vid, count in venue_counts.most_common()
        ],
        first_game_date=games[0].start_date if games else None,
        last_game_date=games[-1].start_date if games else None,
    )


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single team by ID"""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    return team
