import httpx
from sqlalchemy.orm import Session
from typing import Dict, Any
from college_football_tracker.core.config import settings
from college_football_tracker.models.team import Team
from college_football_tracker.models.venue import Venue
from college_football_tracker.models.game import Game
from datetime import datetime


class CollegeFootballDataService:
    """Service to interact with CollegeFootballData.com API"""

    def __init__(self, db: Session):
        self.db = db
        self.base_url = settings.cfb_api_url
        self.api_key = settings.cfb_api_key
        self.headers = {}
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"

    async def _get(self, endpoint: str, params: Dict[str, Any] = None) -> Any:
        """Make GET request to CFB API"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    async def import_teams(self):
        """Import FBS teams from API"""
        teams_data = await self._get("/teams/fbs")

        teams_imported = 0
        for team_data in teams_data:
            # Check if team already exists
            existing_team = self.db.query(Team).filter(
                Team.api_team_id == team_data.get("id")
            ).first()

            if existing_team:
                # Update existing team
                existing_team.school = team_data.get("school")
                existing_team.mascot = team_data.get("mascot")
                existing_team.abbreviation = team_data.get("abbreviation")
                existing_team.conference = team_data.get("conference")
                existing_team.division = team_data.get("division")
            else:
                # Create new team
                team = Team(
                    api_team_id=team_data.get("id"),
                    school=team_data.get("school"),
                    mascot=team_data.get("mascot"),
                    abbreviation=team_data.get("abbreviation"),
                    conference=team_data.get("conference"),
                    division=team_data.get("division")
                )
                self.db.add(team)
                teams_imported += 1

        self.db.commit()
        return teams_imported

    async def import_venues(self):
        """Import venues from API"""
        venues_data = await self._get("/venues")

        venues_imported = 0
        for venue_data in venues_data:
            # Check if venue already exists
            existing_venue = self.db.query(Venue).filter(
                Venue.api_venue_id == venue_data.get("id")
            ).first()

            if existing_venue:
                # Update existing venue
                existing_venue.name = venue_data.get("name")
                existing_venue.city = venue_data.get("city")
                existing_venue.state = venue_data.get("state")
                existing_venue.capacity = venue_data.get("capacity")
            else:
                # Create new venue
                venue = Venue(
                    api_venue_id=venue_data.get("id"),
                    name=venue_data.get("name"),
                    city=venue_data.get("city"),
                    state=venue_data.get("state"),
                    capacity=venue_data.get("capacity")
                )
                self.db.add(venue)
                venues_imported += 1

        self.db.commit()
        return venues_imported

    async def import_season_data(self, season: int):
        """Import all games for a given season"""
        # First ensure teams and venues are imported
        teams_imported = await self.import_teams()
        venues_imported = await self.import_venues()

        # Get games for the season
        games_data = await self._get("/games", params={
            "year": season,
            "seasonType": "both",
            "division": "fbs"
        })

        games_imported = 0
        for game_data in games_data:
            # Get team IDs
            home_team = self.db.query(Team).filter(
                Team.school == game_data.get("homeTeam")
            ).first()
            away_team = self.db.query(Team).filter(
                Team.school == game_data.get("awayTeam")
            ).first()

            if not home_team or not away_team:
                continue  # Skip if teams not found

            # Get venue ID if available
            venue_id = None
            if game_data.get("venueId"):
                venue = self.db.query(Venue).filter(
                    Venue.api_venue_id == game_data.get("venueId")
                ).first()
                if venue:
                    venue_id = venue.id

            # Check if game already exists
            existing_game = self.db.query(Game).filter(
                Game.api_game_id == game_data.get("id")
            ).first()

            # Parse date
            game_date = None
            if game_data.get("startDate"):
                try:
                    game_date = datetime.fromisoformat(
                        game_data.get("startDate").replace("Z", "+00:00")
                    ).date()
                except:
                    pass

            if existing_game:
                # Update existing game
                existing_game.home_score = game_data.get("homePoints")
                existing_game.away_score = game_data.get("awayPoints")
                existing_game.game_date = game_date
                existing_game.week = game_data.get("week")
                existing_game.venue_id = venue_id
                existing_game.attendance = game_data.get("attendance")
            else:
                # Create new game
                game = Game(
                    api_game_id=game_data.get("id"),
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    home_score=game_data.get("homePoints"),
                    away_score=game_data.get("awayPoints"),
                    game_date=game_date,
                    season=season,
                    week=game_data.get("week"),
                    venue_id=venue_id,
                    attendance=game_data.get("attendance")
                )
                self.db.add(game)
                games_imported += 1

        self.db.commit()

        return {
            "teams_imported": teams_imported,
            "venues_imported": venues_imported,
            "games_imported": games_imported
        }
