from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class TeamRecord:
    team_id: int
    name: str
    abbreviation: str | None
    league_name: str | None
    division_name: str | None


@dataclass(frozen=True)
class PlayerRecord:
    player_id: int
    full_name: str
    primary_position: str | None
    bats: str | None
    throws: str | None
    birth_date: date | None
    mlb_debut_date: date | None


@dataclass(frozen=True)
class GameRecord:
    game_pk: int
    game_date: date
    season: int
    game_type: str | None
    status_text: str | None
    home_team_id: int
    away_team_id: int
    home_score: int | None
    away_score: int | None


def _parse_date(value: str | None) -> date | None:
    if value is None or value == "":
        return None
    return date.fromisoformat(value[:10])


def normalize_teams(payload: list[dict[str, Any]]) -> list[TeamRecord]:
    teams: list[TeamRecord] = []
    for team in payload:
        team_id = team.get("id")
        name = team.get("name")
        if not isinstance(team_id, int) or not isinstance(name, str) or name == "":
            continue

        league = team.get("league")
        division = team.get("division")
        league_name = league.get("name") if isinstance(league, dict) else None
        division_name = division.get("name") if isinstance(division, dict) else None
        abbreviation_value = team.get("abbreviation")
        abbreviation = abbreviation_value if isinstance(abbreviation_value, str) else None
        teams.append(
            TeamRecord(
                team_id=team_id,
                name=name,
                abbreviation=abbreviation,
                league_name=league_name if isinstance(league_name, str) else None,
                division_name=division_name if isinstance(division_name, str) else None,
            )
        )
    return teams


def normalize_players(rosters_by_team: dict[str, list[dict[str, Any]]]) -> list[PlayerRecord]:
    player_map: dict[int, PlayerRecord] = {}

    for roster in rosters_by_team.values():
        for row in roster:
            person = row.get("person")
            if not isinstance(person, dict):
                continue
            player_id = person.get("id")
            full_name = person.get("fullName")
            if not isinstance(player_id, int) or not isinstance(full_name, str) or full_name == "":
                continue

            position = row.get("position")
            bats_throws = row.get("batSide"), row.get("pitchHand")
            primary_position = position.get("abbreviation") if isinstance(position, dict) else None

            bats = None
            if isinstance(bats_throws[0], dict):
                code = bats_throws[0].get("code")
                bats = code if isinstance(code, str) else None

            throws = None
            if isinstance(bats_throws[1], dict):
                code = bats_throws[1].get("code")
                throws = code if isinstance(code, str) else None

            player_map[player_id] = PlayerRecord(
                player_id=player_id,
                full_name=full_name,
                primary_position=primary_position if isinstance(primary_position, str) else None,
                bats=bats,
                throws=throws,
                birth_date=None,
                mlb_debut_date=None,
            )

    return list(player_map.values())


def normalize_games(schedule_dates: list[dict[str, Any]]) -> list[GameRecord]:
    games: list[GameRecord] = []
    for day in schedule_dates:
        day_games = day.get("games")
        if not isinstance(day_games, list):
            continue
        for item in day_games:
            if not isinstance(item, dict):
                continue
            game_pk = item.get("gamePk")
            game_date_value = item.get("gameDate") or day.get("date")
            season_value = item.get("season")
            teams = item.get("teams")
            status = item.get("status")
            if not isinstance(game_pk, int):
                continue
            game_date = _parse_date(game_date_value)
            if game_date is None:
                continue
            try:
                season = int(season_value)
            except (TypeError, ValueError):
                continue
            if not isinstance(teams, dict):
                continue

            home = teams.get("home")
            away = teams.get("away")
            if not isinstance(home, dict) or not isinstance(away, dict):
                continue
            home_team_id = _extract_team_id(home)
            away_team_id = _extract_team_id(away)
            if home_team_id is None or away_team_id is None:
                continue

            status_text = status.get("detailedState") if isinstance(status, dict) else None
            game_type_value = item.get("gameType")
            game_type = game_type_value if isinstance(game_type_value, str) else None
            home_score = home.get("score") if isinstance(home.get("score"), int) else None
            away_score = away.get("score") if isinstance(away.get("score"), int) else None

            games.append(
                GameRecord(
                    game_pk=game_pk,
                    game_date=game_date,
                    season=season,
                    game_type=game_type,
                    status_text=status_text if isinstance(status_text, str) else None,
                    home_team_id=home_team_id,
                    away_team_id=away_team_id,
                    home_score=home_score,
                    away_score=away_score,
                )
            )
    return games


def _extract_team_id(team_info: dict[str, Any]) -> int | None:
    team = team_info.get("team")
    if not isinstance(team, dict):
        return None
    team_id = team.get("id")
    return team_id if isinstance(team_id, int) else None
