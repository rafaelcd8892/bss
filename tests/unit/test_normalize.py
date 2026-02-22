from baseball_sim.ingest.normalize import normalize_games, normalize_players, normalize_teams


def test_normalize_teams() -> None:
    payload = [
        {
            "id": 147,
            "name": "New York Yankees",
            "abbreviation": "NYY",
            "league": {"name": "American League"},
            "division": {"name": "AL East"},
        }
    ]
    records = normalize_teams(payload)
    assert len(records) == 1
    assert records[0].team_id == 147
    assert records[0].abbreviation == "NYY"


def test_normalize_players_from_rosters() -> None:
    rosters_by_team = {
        "147": [
            {
                "person": {"id": 592450, "fullName": "Aaron Judge"},
                "position": {"abbreviation": "RF"},
            }
        ]
    }
    players = normalize_players(rosters_by_team)
    assert len(players) == 1
    assert players[0].player_id == 592450
    assert players[0].full_name == "Aaron Judge"
    assert players[0].primary_position == "RF"


def test_normalize_games() -> None:
    schedule_dates = [
        {
            "date": "2026-04-01",
            "games": [
                {
                    "gamePk": 12345,
                    "season": "2026",
                    "gameType": "R",
                    "status": {"detailedState": "Final"},
                    "teams": {
                        "home": {"team": {"id": 147}, "score": 5},
                        "away": {"team": {"id": 121}, "score": 3},
                    },
                }
            ],
        }
    ]
    games = normalize_games(schedule_dates)
    assert len(games) == 1
    assert games[0].game_pk == 12345
    assert games[0].home_team_id == 147
    assert games[0].away_team_id == 121
    assert games[0].home_score == 5
