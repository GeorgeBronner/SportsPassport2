from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from sports_passport.core.dependencies import get_current_user
from sports_passport.db.database import get_db
from sports_passport.models.attendance import UserGameAttendance
from sports_passport.models.game import Game
from sports_passport.models.user import User
from sports_passport.schemas.attendance import (
    AttendanceCreate,
    AttendanceResponse,
    AttendanceStats,
    AttendanceUpdate,
    AttendanceVenueCount,
    AttendanceVenuePoint,
    AttendanceVenuesResponse,
    BulkAttendanceRequest,
    BulkAttendanceResponse,
    SeasonBreakdown,
    TopTeamCount,
)
from sports_passport.services.adapters.local_time import utc_to_eastern

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

# How many teams the stats response carries full identity for. The Stats page
# shows eight; a little headroom costs nothing and avoids a schema change if
# the view grows.
TOP_TEAM_LIMIT = 12


def _with_game_relations(query):
    """Eager-load everything the serializers and aggregation loops touch,
    so listing/stats don't lazy-load per row (N+1)."""
    return query.options(
        joinedload(UserGameAttendance.game).joinedload(Game.league),
        joinedload(UserGameAttendance.game).joinedload(Game.home_team),
        joinedload(UserGameAttendance.game).joinedload(Game.away_team),
        joinedload(UserGameAttendance.game).joinedload(Game.venue),
    )


def _existing_attendance(db: Session, user_id: int, game_id: int):
    """The caller's attendance row for this game, if any.

    Advisory only — it cannot see a row another session has not committed yet,
    which is why both callers still let the unique index have the final say.
    """
    return db.query(UserGameAttendance).filter(
        UserGameAttendance.user_id == user_id,
        UserGameAttendance.game_id == game_id,
    ).first()


@router.post("/", response_model=AttendanceResponse, status_code=status.HTTP_201_CREATED)
def mark_game_attended(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a game as attended by the current user"""
    # Check if game exists
    game = db.query(Game).filter(Game.id == attendance_data.game_id).first()
    if not game:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found"
        )

    # Check if already marked as attended
    existing = _existing_attendance(db, current_user.id, attendance_data.game_id)

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game already marked as attended"
        )

    # Create attendance record
    attendance = UserGameAttendance(
        user_id=current_user.id,
        game_id=attendance_data.game_id,
        notes=attendance_data.notes
    )

    db.add(attendance)
    try:
        db.commit()
    except IntegrityError as e:
        # Lost the race against a concurrent request for the same game — the
        # unique index caught what the check above couldn't.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Game already marked as attended"
        ) from e
    db.refresh(attendance)

    return attendance


@router.get("/", response_model=list[AttendanceResponse])
def list_attended_games(
    skip: int = 0,
    limit: int = 10000,  # High default limit to return all games for personal/family use
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all games attended by the current user"""
    attendances = _with_game_relations(
        db.query(UserGameAttendance).filter(
            UserGameAttendance.user_id == current_user.id
        )
    ).order_by(UserGameAttendance.created_at.desc()).offset(skip).limit(limit).all()

    return attendances


@router.get("/stats", response_model=AttendanceStats)
def get_attendance_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get attendance statistics for the current user"""
    # Get all attended games with related data
    attendances = _with_game_relations(
        db.query(UserGameAttendance).filter(
            UserGameAttendance.user_id == current_user.id
        )
    ).all()

    if not attendances:
        return AttendanceStats(
            total_games=0,
            unique_stadiums=0,
            unique_states=0,
            games_by_league={},
            games_by_team={},
            games_by_season={},
            stadiums_visited=[],
            states_visited=[]
        )

    # Calculate statistics. Venue uniqueness is by id, not name — distinct
    # venues sharing a name (two "Memorial Stadium"s) must count separately.
    total_games = len(attendances)
    games_by_league = defaultdict(int)
    games_by_team = defaultdict(int)
    games_by_season = defaultdict(int)
    games_by_state = defaultdict(int)
    team_counts = defaultdict(int)
    team_info = {}
    games_by_weekday = defaultdict(int)
    games_by_month = defaultdict(int)
    venue_counts = defaultdict(int)
    venue_info = {}
    first_date = last_date = None
    stadiums = set()
    states = set()
    home_wins = home_losses = home_ties = 0
    season_games = defaultdict(int)
    season_leagues = defaultdict(lambda: defaultdict(int))
    season_venues = defaultdict(set)
    season_home_record = defaultdict(lambda: [0, 0, 0])
    # First season each venue appears in, so a venue counts as "new" once only —
    # and in the right season even if the log is walked out of order.
    venue_first_season = {}

    def _counts_for_stats(team) -> bool:
        # College sports track their top division only (CFB: FBS, CBB: D-I);
        # every pro team counts (classification is null for those leagues).
        if team is None:
            return False
        return team.classification is None or team.classification in ("fbs", "d1")

    for attendance in attendances:
        game = attendance.game
        games_by_season[game.season] += 1
        season_games[game.season] += 1
        # Local wall clock, not the stored UTC instant: a 7:30pm ET kickoff
        # is stored past midnight UTC and would be counted on the next day.
        local = utc_to_eastern(game.start_date)
        games_by_weekday[local.weekday()] += 1
        games_by_month[local.month] += 1
        if game.league:
            games_by_league[game.league.code] += 1
            season_leagues[game.season][game.league.code] += 1

        for team in (game.home_team, game.away_team):
            if not _counts_for_stats(team):
                continue
            games_by_team[team.name] += 1
            # Keyed by id, not name: Alabama fields both a CFB and a CBB team,
            # and the name-keyed map silently merges them.
            team_counts[team.id] += 1
            team_info[team.id] = (team, game.league.code if game.league else "")

        # Home-team record. Only played games count — a future fixture on the
        # log has both scores null and must not be scored as a tie.
        if game.home_score is not None and game.away_score is not None:
            if game.home_score > game.away_score:
                home_wins += 1
                season_home_record[game.season][0] += 1
            elif game.home_score < game.away_score:
                home_losses += 1
                season_home_record[game.season][1] += 1
            else:
                home_ties += 1
                season_home_record[game.season][2] += 1

        # Track stadiums and states
        if game.venue:
            stadiums.add(game.venue.name)
            venue_counts[game.venue.id] += 1
            venue_info[game.venue.id] = game.venue
            season_venues[game.season].add(game.venue.id)
            known = venue_first_season.get(game.venue.id)
            if known is None or game.season < known:
                venue_first_season[game.venue.id] = game.season
            if game.venue.state:
                states.add(game.venue.state)
                games_by_state[game.venue.state] += 1

        if first_date is None or game.start_date < first_date:
            first_date = game.start_date
        if last_date is None or game.start_date > last_date:
            last_date = game.start_date

    top_teams = [
        TopTeamCount(
            team_id=tid,
            name=team_info[tid][0].name,
            league_code=team_info[tid][1],
            logo_url=team_info[tid][0].logo_url,
            abbreviation=team_info[tid][0].abbreviation,
            count=count,
        )
        for tid, count in sorted(
            team_counts.items(), key=lambda x: (-x[1], team_info[x[0]][0].name)
        )[:TOP_TEAM_LIMIT]
    ]

    new_venues_by_season = defaultdict(int)
    for season in venue_first_season.values():
        new_venues_by_season[season] += 1

    # Longest stretch between consecutive attended games. Measured on local
    # calendar days, but the *reported* endpoints stay the stored UTC instants —
    # they are serialized with a trailing Z, so handing back an Eastern wall
    # clock would have the client shift them a second time.
    longest_gap_days = longest_gap_start = longest_gap_end = None
    stored_dates = sorted(a.game.start_date for a in attendances)
    # strict=False on purpose: the offset slice is always one shorter.
    for earlier, later in zip(stored_dates, stored_dates[1:], strict=False):
        # Calendar days, not elapsed time: two games 83h apart are "4 days
        # apart" to a reader, and raw timedelta.days would floor that to 3.
        gap = (utc_to_eastern(later).date() - utc_to_eastern(earlier).date()).days
        if longest_gap_days is None or gap > longest_gap_days:
            longest_gap_days = gap
            longest_gap_start = earlier
            longest_gap_end = later

    venues = [
        AttendanceVenueCount(
            venue_id=vid,
            name=venue_info[vid].name,
            city=venue_info[vid].city,
            state=venue_info[vid].state,
            count=count,
        )
        for vid, count in sorted(
            venue_counts.items(), key=lambda x: (-x[1], venue_info[x[0]].name)
        )
    ]

    return AttendanceStats(
        total_games=total_games,
        unique_stadiums=len(venue_counts),
        unique_states=len(states),
        games_by_league=dict(sorted(games_by_league.items())),
        games_by_team=dict(sorted(games_by_team.items(), key=lambda x: x[1], reverse=True)),
        games_by_season=dict(sorted(games_by_season.items())),
        stadiums_visited=sorted(stadiums),
        states_visited=sorted(states),
        games_by_state=dict(sorted(games_by_state.items())),
        venues=venues,
        first_game_date=first_date,
        last_game_date=last_date,
        home_wins=home_wins,
        home_losses=home_losses,
        home_ties=home_ties,
        games_by_weekday=dict(sorted(games_by_weekday.items())),
        games_by_month=dict(sorted(games_by_month.items())),
        season_breakdown={
            season: SeasonBreakdown(
                games=count,
                venues=len(season_venues[season]),
                leagues=dict(
                    sorted(season_leagues[season].items(), key=lambda x: (-x[1], x[0]))
                ),
                home_wins=season_home_record[season][0],
                home_losses=season_home_record[season][1],
                home_ties=season_home_record[season][2],
            )
            for season, count in sorted(season_games.items())
        },
        top_teams=top_teams,
        new_venues_by_season=dict(sorted(new_venues_by_season.items())),
        longest_gap_days=longest_gap_days,
        longest_gap_start=longest_gap_start,
        longest_gap_end=longest_gap_end,
    )


@router.get("/venues", response_model=AttendanceVenuesResponse)
def get_attendance_venues(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Venues the user has attended games at, with coordinates — feeds the map view."""
    attendances = _with_game_relations(
        db.query(UserGameAttendance).filter(
            UserGameAttendance.user_id == current_user.id
        )
    ).all()

    counts = defaultdict(int)
    league_counts = defaultdict(lambda: defaultdict(int))
    venues_by_id = {}
    without_venue = 0

    for attendance in attendances:
        game = attendance.game
        if not game.venue:
            without_venue += 1
            continue
        venue = game.venue
        counts[venue.id] += 1
        venues_by_id[venue.id] = venue
        if game.league:
            league_counts[venue.id][game.league.code] += 1

    points = [
        AttendanceVenuePoint(
            venue_id=vid,
            name=venues_by_id[vid].name,
            city=venues_by_id[vid].city,
            state=venues_by_id[vid].state,
            latitude=venues_by_id[vid].latitude,
            longitude=venues_by_id[vid].longitude,
            count=count,
            leagues=[
                code for code, _ in
                sorted(league_counts[vid].items(), key=lambda x: (-x[1], x[0]))
            ],
        )
        for vid, count in sorted(
            counts.items(), key=lambda x: (-x[1], venues_by_id[x[0]].name)
        )
    ]

    return AttendanceVenuesResponse(venues=points, games_without_venue=without_venue)


@router.patch("/{attendance_id}", response_model=AttendanceResponse)
def update_attendance(
    attendance_id: int,
    attendance_data: AttendanceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update attendance notes"""
    attendance = db.query(UserGameAttendance).filter(
        UserGameAttendance.id == attendance_id,
        UserGameAttendance.user_id == current_user.id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )

    # exclude_unset distinguishes "notes omitted" from an explicit null,
    # so clients can clear a note by sending notes: null.
    update = attendance_data.model_dump(exclude_unset=True)
    if "notes" in update:
        attendance.notes = update["notes"]

    db.commit()
    db.refresh(attendance)

    return attendance


@router.delete("/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove a game from attended list"""
    attendance = db.query(UserGameAttendance).filter(
        UserGameAttendance.id == attendance_id,
        UserGameAttendance.user_id == current_user.id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )

    db.delete(attendance)
    db.commit()

    return None


@router.post("/bulk", response_model=BulkAttendanceResponse, status_code=status.HTTP_201_CREATED)
def mark_games_bulk_attended(
    bulk_request: BulkAttendanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark multiple games as attended in a single request"""
    created = 0
    skipped = 0
    errors = []
    # Games staged by this request. The session doesn't autoflush, so a game
    # listed twice in one payload isn't visible to the existing-row query below
    # and would otherwise violate the unique index at commit time.
    pending: set[int] = set()

    for item in bulk_request.games:
        try:
            # Check if game exists
            game = db.query(Game).filter(Game.id == item.game_id).first()
            if not game:
                errors.append(f"Game {item.game_id} not found")
                continue

            # Check if already marked as attended
            existing = _existing_attendance(db, current_user.id, item.game_id)

            if existing or item.game_id in pending:
                skipped += 1
                continue

            pending.add(item.game_id)

            # Create attendance record inside a savepoint, so a row that loses
            # the race against a *concurrent* bulk request costs only itself.
            # The lookup above can't see uncommitted work in another session,
            # so without this the unique index would abort the whole
            # transaction at commit and drop every good row with it.
            try:
                with db.begin_nested():
                    db.add(
                        UserGameAttendance(
                            user_id=current_user.id,
                            game_id=item.game_id,
                            notes=item.notes
                        )
                    )
            except IntegrityError:
                # Someone else committed this pair first. It stays in `pending`
                # so a later copy in this same payload is skipped too, rather
                # than burning another savepoint to rediscover the conflict.
                skipped += 1
                continue

            created += 1

        except Exception as e:
            errors.append(f"Game {item.game_id}: {str(e)}")
            continue

    # Commit all at once
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save attendance records: {str(e)}"
        ) from e

    return BulkAttendanceResponse(
        created=created,
        skipped=skipped,
        errors=errors
    )
