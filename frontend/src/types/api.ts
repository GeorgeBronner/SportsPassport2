// User types
export interface User {
  id: number;
  email: string;
  full_name: string;
  is_admin: boolean;
  created_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

// League types
export interface League {
  id: number;
  code: string;
  name: string;
  sport: string;
  active: boolean;
}

// Team types
export interface Team {
  id: number;
  league_id: number;
  name: string;
  nickname: string | null;
  abbreviation: string | null;
  city: string | null;
  state: string | null;
  conference: string | null;
  division: string | null;
  classification: string | null;
  first_season: number | null;
  last_season: number | null;
  franchise_id: number | null;
  logo_url: string | null;
}

export interface TeamSearchResult extends Team {
  league_code: string;
  attended_count: number;
}

export interface TeamVenueCount {
  name: string;
  city: string | null;
  state: string | null;
  count: number;
}

export interface TeamAttendanceStats {
  team_id: number;
  games_attended: number;
  wins: number;
  losses: number;
  ties: number;
  games_by_season: Record<number, number>;
  venues: TeamVenueCount[];
  first_game_date: string | null;
  last_game_date: string | null;
}

// Venue types
export interface Venue {
  id: number;
  name: string;
  city: string | null;
  state: string | null;
  country: string | null;
  capacity: number | null;
}

// Game types
export interface Game {
  id: number;
  league: League;
  start_date: string;  // ISO datetime string (UTC)
  has_time: boolean;
  season: number;
  season_type: string | null;
  week: number | null;
  home_team_id: number;
  away_team_id: number;
  home_score: number | null;
  away_score: number | null;
  venue_id: number | null;
  neutral_site: boolean;
  overtime_flag: string | null;
  home_team: Team;
  away_team: Team;
  venue: Venue | null;
  attendance?: number | null;
}

export interface GameListItem {
  id: number;
  league: League;
  start_date: string;  // ISO datetime string (UTC)
  has_time: boolean;
  season: number;
  season_type: string | null;
  week: number | null;
  neutral_site: boolean;
  overtime_flag: string | null;
  home_team: Team;
  away_team: Team;
  home_score: number | null;
  away_score: number | null;
  venue: Venue | null;
}

export interface SeasonInfo {
  season: number;
  game_count: number;
}

// Attendance types
export interface Attendance {
  id: number;
  user_id: number;
  game_id: number;
  notes: string | null;
  created_at: string;
  game: GameListItem;
}

export interface AttendanceCreate {
  game_id: number;
  notes?: string;
}

export interface AttendanceUpdate {
  notes?: string;
}

export interface AttendanceStats {
  total_games: number;
  unique_stadiums: number;
  unique_states: number;
  games_by_league: Record<string, number>;
  games_by_team: Record<string, number>;
  games_by_season: Record<number, number>;
  stadiums_visited: string[];
  states_visited: string[];
  games_by_state: Record<string, number>;
  venues: TeamVenueCount[];
  first_game_date: string | null;
  last_game_date: string | null;
}

export interface BulkAttendanceItem {
  game_id: number;
  notes?: string;
}

export interface BulkAttendanceRequest {
  games: BulkAttendanceItem[];
}

export interface BulkAttendanceResponse {
  created: number;
  skipped: number;
  errors: string[];
}

// Admin / import types
export interface ImportResult {
  league: string;
  teams_imported: number;
  venues_imported: number;
  games_imported: number;
  games_updated: number;
  errors: string[];
}

export interface AdminStatusRow {
  league: string;
  adapter_available: boolean;
  teams: number;
  games: number;
  first_season: number | null;
  last_season: number | null;
}

// Filter types
export interface GameFilters {
  league?: string;
  season?: number;
  team?: string;
  skip?: number;
  limit?: number;
}

export interface TeamFilters {
  league?: string;
  conference?: string;
  search?: string;
  franchise_id?: number;
}
