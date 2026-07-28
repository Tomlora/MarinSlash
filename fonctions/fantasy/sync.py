from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import text

from .database import transaction
from .models import Competition
from .providers.base import PlayerProvider, ProviderPlayer, ProviderTeam


SYNC_COMPETITIONS = (Competition.LEC, Competition.LCS, Competition.LFL)
MIN_TEAMS_PER_COMPETITION = 4
MIN_PLAYERS_PER_COMPETITION = 20


class FantasySyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlayerPoolSyncResult:
    teams_seen: int
    players_seen: int
    histories_opened: int
    histories_closed: int
    teams_deactivated: int
    players_deactivated: int


def _validate_snapshot(
    teams: list[ProviderTeam], players: list[ProviderPlayer]
) -> None:
    team_counts = Counter(team.competition for team in teams)
    player_counts = Counter(player.competition for player in players)

    problems: list[str] = []
    for competition in SYNC_COMPETITIONS:
        if team_counts[competition] < MIN_TEAMS_PER_COMPETITION:
            problems.append(
                f"{competition.value}: {team_counts[competition]} équipes"
            )
        if player_counts[competition] < MIN_PLAYERS_PER_COMPETITION:
            problems.append(
                f"{competition.value}: {player_counts[competition]} joueurs"
            )

    if problems:
        raise FantasySyncError(
            "Snapshot externe incomplet, synchronisation annulée ("
            + "; ".join(problems)
            + ")."
        )

    team_keys = {(team.competition, team.external_id) for team in teams}
    orphan_players = [
        player.handle
        for player in players
        if (player.competition, player.team_external_id) not in team_keys
    ]
    if orphan_players:
        raise FantasySyncError(
            "Snapshot incohérent : certains joueurs n'ont pas d'équipe importée."
        )


async def sync_player_pool(provider: PlayerProvider) -> PlayerPoolSyncResult:
    """Synchronise équipes, joueurs et tenures actuelles de LEC/LCS/LFL.

    Le provider est lu entièrement avant toute écriture. Un snapshot trop petit
    ou incohérent provoque un abort avant la transaction, ce qui évite de
    désactiver des joueurs à cause d'une réponse externe partielle.
    """

    teams = list(await provider.fetch_teams(SYNC_COMPETITIONS))
    players = list(await provider.fetch_players(SYNC_COMPETITIONS))
    _validate_snapshot(teams, players)

    histories_opened = 0
    histories_closed = 0
    teams_deactivated = 0
    players_deactivated = 0

    with transaction() as connection:
        team_ids: dict[tuple[Competition, str], int] = {}
        seen_team_ids: set[int] = set()

        for team in teams:
            row = connection.execute(
                text(
                    """
                    INSERT INTO fantasy.pro_team
                        (competition_code, external_id, name, short_name, active, updated_at)
                    VALUES
                        (:competition_code, :external_id, :name, :short_name, TRUE, NOW())
                    ON CONFLICT (competition_code, external_id) DO UPDATE
                    SET
                        name = EXCLUDED.name,
                        short_name = EXCLUDED.short_name,
                        active = TRUE,
                        updated_at = NOW()
                    RETURNING id
                    """
                ),
                {
                    "competition_code": team.competition.value,
                    "external_id": team.external_id,
                    "name": team.name,
                    "short_name": team.short_name,
                },
            ).one()
            team_id = int(row.id)
            team_ids[(team.competition, team.external_id)] = team_id
            seen_team_ids.add(team_id)

        existing_target_teams = connection.execute(
            text(
                """
                SELECT id
                FROM fantasy.pro_team
                WHERE competition_code IN ('LEC', 'LCS', 'LFL')
                  AND active = TRUE
                """
            )
        ).all()
        for row in existing_target_teams:
            team_id = int(row.id)
            if team_id not in seen_team_ids:
                connection.execute(
                    text(
                        "UPDATE fantasy.pro_team SET active = FALSE, updated_at = NOW() WHERE id = :team_id"
                    ),
                    {"team_id": team_id},
                )
                teams_deactivated += 1

        player_ids: dict[str, int] = {}
        seen_player_ids: set[int] = set()

        for player in players:
            row = connection.execute(
                text(
                    """
                    INSERT INTO fantasy.pro_player
                        (external_id, handle, role, active, updated_at)
                    VALUES
                        (:external_id, :handle, :role, TRUE, NOW())
                    ON CONFLICT (external_id) DO UPDATE
                    SET
                        handle = EXCLUDED.handle,
                        role = EXCLUDED.role,
                        active = TRUE,
                        updated_at = NOW()
                    RETURNING id
                    """
                ),
                {
                    "external_id": player.external_id,
                    "handle": player.handle,
                    "role": player.role.value,
                },
            ).one()
            player_id = int(row.id)
            player_ids[player.external_id] = player_id
            seen_player_ids.add(player_id)

            desired_team_id = team_ids[(player.competition, player.team_external_id)]
            active_histories = connection.execute(
                text(
                    """
                    SELECT id, team_id
                    FROM fantasy.pro_player_team_history
                    WHERE player_id = :player_id AND valid_until IS NULL
                    FOR UPDATE
                    """
                ),
                {"player_id": player_id},
            ).all()

            desired_is_open = False
            for history in active_histories:
                if int(history.team_id) == desired_team_id:
                    desired_is_open = True
                    continue
                connection.execute(
                    text(
                        """
                        UPDATE fantasy.pro_player_team_history
                        SET valid_until = NOW()
                        WHERE id = :history_id AND valid_until IS NULL
                        """
                    ),
                    {"history_id": int(history.id)},
                )
                histories_closed += 1

            if not desired_is_open:
                connection.execute(
                    text(
                        """
                        INSERT INTO fantasy.pro_player_team_history
                            (player_id, team_id, valid_from)
                        VALUES
                            (:player_id, :team_id, NOW())
                        """
                    ),
                    {"player_id": player_id, "team_id": desired_team_id},
                )
                histories_opened += 1

        active_target_histories = connection.execute(
            text(
                """
                SELECT history.id, history.player_id
                FROM fantasy.pro_player_team_history history
                JOIN fantasy.pro_team team ON team.id = history.team_id
                WHERE history.valid_until IS NULL
                  AND team.competition_code IN ('LEC', 'LCS', 'LFL')
                FOR UPDATE OF history
                """
            )
        ).all()

        stale_player_ids: set[int] = set()
        for history in active_target_histories:
            player_id = int(history.player_id)
            if player_id in seen_player_ids:
                continue
            connection.execute(
                text(
                    """
                    UPDATE fantasy.pro_player_team_history
                    SET valid_until = NOW()
                    WHERE id = :history_id AND valid_until IS NULL
                    """
                ),
                {"history_id": int(history.id)},
            )
            stale_player_ids.add(player_id)
            histories_closed += 1

        for player_id in stale_player_ids:
            still_has_team = bool(
                connection.execute(
                    text(
                        """
                        SELECT EXISTS (
                            SELECT 1
                            FROM fantasy.pro_player_team_history
                            WHERE player_id = :player_id AND valid_until IS NULL
                        )
                        """
                    ),
                    {"player_id": player_id},
                ).scalar_one()
            )
            if not still_has_team:
                connection.execute(
                    text(
                        "UPDATE fantasy.pro_player SET active = FALSE, updated_at = NOW() WHERE id = :player_id"
                    ),
                    {"player_id": player_id},
                )
                players_deactivated += 1

    return PlayerPoolSyncResult(
        teams_seen=len(teams),
        players_seen=len(players),
        histories_opened=histories_opened,
        histories_closed=histories_closed,
        teams_deactivated=teams_deactivated,
        players_deactivated=players_deactivated,
    )
