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

// Team types
export interface Team {
  id: number;
  school: string;
  mascot: string | null;
  abbreviation: string | null;
  conference: string | null;
  division: string | null;
  classification: string | null;
  api_team_id: number | null;
}

// Venue types
export interface Venue {
  id: number;
  name: string;
  city: string | null;
  state: string | null;
  capacity: number | null;
  api_venue_id: number | null;
}

// Game types
export interface Game {
  id: number;
  start_date: string;  // ISO datetime string (UTC)
  season: number;
  season_type: string | null;
  week: number | null;
  home_team_id: number;
  away_team_id: number;
  home_score: number | null;
  away_score: number | null;
  venue_id: number | null;
  api_game_id: number | null;
  home_team: Team;
  away_team: Team;
  venue: Venue | null;
  attendance?: number | null;
}

export interface GameListItem {
  id: number;
  start_date: string;  // ISO datetime string (UTC)
  season: number;
  season_type: string | null;
  week: number | null;
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
  games_by_team: Record<string, number>;
  games_by_season: Record<number, number>;
  stadiums_visited: string[];
  states_visited: string[];
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

// Filter types
export interface GameFilters {
  season?: number;
  team?: string;
  skip?: number;
  limit?: number;
}

export interface TeamFilters {
  conference?: string;
  search?: string;
}
