from __future__ import annotations

from dataclasses import dataclass
from secrets import SystemRandom
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from .database import get_engine, transaction
from .draft import ROUNDS, can_still_complete_roster, manager_for_pick, remaining_picks_for_manager
from .models import Competition, PlayerAsset, PlayerRole, TeamAsset
from .roster import RosterValidationError, choose_initial_roster


class FantasyServiceError(ValueError):
    """User-facing Fantasy rule or state error."""


@dataclass(frozen=True)
class ManagerView:
    manager_id: int
    discord_user_id: int
    draft_position: Optional[int]


@dataclass(frozen=True)
class LeagueView:
    league_id: int
    name: str
    status: str
    owner_discord_id: int
    scoring_mode: str
    max_managers: int
    season_id: int
    season_name: str
    managers: tuple[ManagerView, ...]


@dataclass(frozen=True)
class PickView:
    overall_pick: int
    round_number: int
    manager_id: int
    discord_user_id: int
    asset_type: str
    asset_name: str


@dataclass(frozen=True)
class DraftBoardView:
    league: LeagueView
    draft_id: Optional[int]
    draft_status: str
    total_picks: int
    completed_picks: int
    next_manager: Optional[ManagerView]
    picks: tuple[PickView, ...]


@dataclass(frozen=True)
class PickResult:
    pick: PickView
    draft_completed: bool


def _clean_name(value: str, field: str, max_length: int = 80) -> str:
    value = " ".join(str(value or "").split())
    if not value:
        raise FantasyServiceError(f"{field} ne peut pas être vide.")
    if len(value) > max_length:
        raise FantasyServiceError(f"{field} est limité à {max_length} caractères.")
    return value


def _league_row(
    connection: Connection, league_id: int, guild_id: int, *, for_update: bool = False
):
    suffix = " FOR UPDATE" if for_update else ""
    row = connection.execute(
        text(
            """
            SELECT id, guild_id, name, owner_discord_id, status, scoring_mode, max_managers
            FROM fantasy.league
            WHERE id = :league_id AND guild_id = :guild_id
            """
            + suffix
        ),
        {"league_id": league_id, "guild_id": guild_id},
    ).first()
    if row is None:
        raise FantasyServiceError("Fantasy introuvable sur ce serveur.")
    return row


def _current_season_row(connection: Connection, league_id: int):
    row = connection.execute(
        text(
            """
            SELECT id, name, scoring_rule_version, starts_at, ends_at
            FROM fantasy.season
            WHERE league_id = :league_id
            ORDER BY id DESC
            LIMIT 1
            """
        ),
        {"league_id": league_id},
    ).first()
    if row is None:
        raise FantasyServiceError("Aucune saison n'est configurée pour cette Fantasy.")
    return row


def _manager_rows(connection: Connection, league_id: int, *, for_update: bool = False):
    suffix = " FOR UPDATE" if for_update else ""
    return connection.execute(
        text(
            """
            SELECT id, discord_user_id, draft_position, joined_at
            FROM fantasy.manager
            WHERE league_id = :league_id
            ORDER BY draft_position NULLS LAST, joined_at, id
            """
            + suffix
        ),
        {"league_id": league_id},
    ).all()


def _manager_views(rows) -> tuple[ManagerView, ...]:
    return tuple(
        ManagerView(
            manager_id=int(row.id),
            discord_user_id=int(row.discord_user_id),
            draft_position=int(row.draft_position) if row.draft_position is not None else None,
        )
        for row in rows
    )


def create_league(
    *,
    guild_id: int,
    owner_discord_id: int,
    name: str,
    season_name: str = "Saison 1",
    max_managers: int = 8,
    scoring_mode: str = "classic_sum",
) -> LeagueView:
    name = _clean_name(name, "Le nom de la Fantasy")
    season_name = _clean_name(season_name, "Le nom de la saison")
    if not 2 <= int(max_managers) <= 8:
        raise FantasyServiceError("Une Fantasy doit accepter entre 2 et 8 managers.")
    if scoring_mode not in {"classic_sum", "normalized"}:
        raise FantasyServiceError("Mode de scoring inconnu.")

    try:
        with transaction() as connection:
            league = connection.execute(
                text(
                    """
                    INSERT INTO fantasy.league
                        (guild_id, name, owner_discord_id, scoring_mode, max_managers)
                    VALUES
                        (:guild_id, :name, :owner_discord_id, :scoring_mode, :max_managers)
                    RETURNING id
                    """
                ),
                {
                    "guild_id": guild_id,
                    "name": name,
                    "owner_discord_id": owner_discord_id,
                    "scoring_mode": scoring_mode,
                    "max_managers": max_managers,
                },
            ).one()
            league_id = int(league.id)
            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.season (league_id, name)
                    VALUES (:league_id, :season_name)
                    """
                ),
                {"league_id": league_id, "season_name": season_name},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.manager (league_id, discord_user_id)
                    VALUES (:league_id, :discord_user_id)
                    """
                ),
                {"league_id": league_id, "discord_user_id": owner_discord_id},
            )
    except IntegrityError as exc:
        raise FantasyServiceError(
            "Une Fantasy portant ce nom existe déjà sur ce serveur."
        ) from exc

    return get_league(league_id=league_id, guild_id=guild_id)


def join_league(*, league_id: int, guild_id: int, discord_user_id: int) -> LeagueView:
    try:
        with transaction() as connection:
            league = _league_row(connection, league_id, guild_id, for_update=True)
            if league.status != "registration":
                raise FantasyServiceError("Les inscriptions de cette Fantasy sont fermées.")

            existing = connection.execute(
                text(
                    """
                    SELECT id
                    FROM fantasy.manager
                    WHERE league_id = :league_id AND discord_user_id = :discord_user_id
                    """
                ),
                {"league_id": league_id, "discord_user_id": discord_user_id},
            ).first()
            if existing is not None:
                raise FantasyServiceError("Tu es déjà inscrit dans cette Fantasy.")

            manager_count = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM fantasy.manager WHERE league_id = :league_id"),
                    {"league_id": league_id},
                ).scalar_one()
            )
            if manager_count >= int(league.max_managers):
                raise FantasyServiceError("Cette Fantasy a déjà atteint sa limite de managers.")

            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.manager (league_id, discord_user_id)
                    VALUES (:league_id, :discord_user_id)
                    """
                ),
                {"league_id": league_id, "discord_user_id": discord_user_id},
            )
    except IntegrityError as exc:
        raise FantasyServiceError("Impossible de rejoindre cette Fantasy.") from exc

    return get_league(league_id=league_id, guild_id=guild_id)


def get_league(*, league_id: int, guild_id: int) -> LeagueView:
    with get_engine().connect() as connection:
        league = _league_row(connection, league_id, guild_id)
        season = _current_season_row(connection, league_id)
        managers = _manager_views(_manager_rows(connection, league_id))
        return LeagueView(
            league_id=int(league.id),
            name=str(league.name),
            status=str(league.status),
            owner_discord_id=int(league.owner_discord_id),
            scoring_mode=str(league.scoring_mode),
            max_managers=int(league.max_managers),
            season_id=int(season.id),
            season_name=str(season.name),
            managers=managers,
        )


def start_draft(
    *, league_id: int, guild_id: int, requester_discord_id: int
) -> DraftBoardView:
    with transaction() as connection:
        league = _league_row(connection, league_id, guild_id, for_update=True)
        if int(league.owner_discord_id) != int(requester_discord_id):
            raise FantasyServiceError("Seul le créateur de la Fantasy peut lancer le draft.")
        if league.status != "registration":
            raise FantasyServiceError("Cette Fantasy n'est plus en phase d'inscription.")

        season = _current_season_row(connection, league_id)
        managers = list(_manager_rows(connection, league_id, for_update=True))
        if len(managers) < 2:
            raise FantasyServiceError("Il faut au moins 2 managers pour lancer le draft.")
        if len(managers) > int(league.max_managers):
            raise FantasyServiceError("La Fantasy contient trop de managers.")

        shuffled = list(managers)
        SystemRandom().shuffle(shuffled)
        for draft_position, manager in enumerate(shuffled, start=1):
            connection.execute(
                text(
                    """
                    UPDATE fantasy.manager
                    SET draft_position = :draft_position
                    WHERE id = :manager_id
                    """
                ),
                {"draft_position": draft_position, "manager_id": int(manager.id)},
            )

        existing_draft = connection.execute(
            text("SELECT id, status FROM fantasy.draft WHERE season_id = :season_id FOR UPDATE"),
            {"season_id": int(season.id)},
        ).first()
        if existing_draft is None:
            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.draft (season_id, status, rounds, started_at)
                    VALUES (:season_id, 'active', :rounds, NOW())
                    """
                ),
                {"season_id": int(season.id), "rounds": ROUNDS},
            )
        elif existing_draft.status == "pending":
            connection.execute(
                text(
                    """
                    UPDATE fantasy.draft
                    SET status = 'active', started_at = NOW(), completed_at = NULL
                    WHERE id = :draft_id
                    """
                ),
                {"draft_id": int(existing_draft.id)},
            )
        else:
            raise FantasyServiceError("Un draft a déjà été lancé pour cette saison.")

        connection.execute(
            text("UPDATE fantasy.league SET status = 'draft' WHERE id = :league_id"),
            {"league_id": league_id},
        )

    return get_draft_board(league_id=league_id, guild_id=guild_id)


def _resolve_player(connection: Connection, asset_name: str):
    rows = connection.execute(
        text(
            """
            SELECT
                p.id,
                p.handle,
                p.role,
                team.competition_code
            FROM fantasy.pro_player p
            JOIN LATERAL (
                SELECT history.team_id
                FROM fantasy.pro_player_team_history history
                WHERE history.player_id = p.id
                  AND history.valid_from <= NOW()
                  AND (history.valid_until IS NULL OR history.valid_until > NOW())
                ORDER BY history.valid_from DESC
                LIMIT 1
            ) current_team ON TRUE
            JOIN fantasy.pro_team team ON team.id = current_team.team_id
            WHERE p.active = TRUE
              AND LOWER(p.handle) = LOWER(:asset_name)
            """
        ),
        {"asset_name": asset_name},
    ).all()
    if not rows:
        raise FantasyServiceError(
            "Joueur introuvable ou sans équipe active dans le pool Fantasy."
        )
    if len(rows) > 1:
        raise FantasyServiceError("Plusieurs joueurs portent ce nom dans le pool Fantasy.")
    return rows[0]


def _resolve_team(connection: Connection, asset_name: str):
    rows = connection.execute(
        text(
            """
            SELECT id, name, short_name, competition_code
            FROM fantasy.pro_team
            WHERE active = TRUE
              AND (
                    LOWER(name) = LOWER(:asset_name)
                 OR LOWER(COALESCE(short_name, '')) = LOWER(:asset_name)
                 OR LOWER(external_id) = LOWER(:asset_name)
              )
            """
        ),
        {"asset_name": asset_name},
    ).all()
    if not rows:
        raise FantasyServiceError("Équipe introuvable dans le pool Fantasy.")
    if len(rows) > 1:
        raise FantasyServiceError("Plusieurs équipes correspondent à ce nom.")
    return rows[0]


def _manager_pick_assets(connection: Connection, draft_id: int, manager_id: int):
    return connection.execute(
        text(
            """
            SELECT
                dp.overall_pick,
                dp.player_id,
                dp.team_id,
                p.role,
                player_team.competition_code AS player_competition,
                drafted_team.competition_code AS team_competition
            FROM fantasy.draft_pick dp
            LEFT JOIN fantasy.pro_player p ON p.id = dp.player_id
            LEFT JOIN LATERAL (
                SELECT team.competition_code
                FROM fantasy.pro_player_team_history history
                JOIN fantasy.pro_team team ON team.id = history.team_id
                WHERE history.player_id = dp.player_id
                  AND history.valid_from <= NOW()
                  AND (history.valid_until IS NULL OR history.valid_until > NOW())
                ORDER BY history.valid_from DESC
                LIMIT 1
            ) player_team ON TRUE
            LEFT JOIN fantasy.pro_team drafted_team ON drafted_team.id = dp.team_id
            WHERE dp.draft_id = :draft_id AND dp.manager_id = :manager_id
            ORDER BY dp.overall_pick
            """
        ),
        {"draft_id": draft_id, "manager_id": manager_id},
    ).all()


def _validate_candidate(
    *,
    manager_ids: list[int],
    manager_id: int,
    overall_pick: int,
    current_assets,
    candidate_type: str,
    candidate_role: Optional[str],
    candidate_competition: str,
) -> None:
    player_rows = [row for row in current_assets if row.player_id is not None]
    team_rows = [row for row in current_assets if row.team_id is not None]

    if candidate_type == "player" and len(player_rows) >= 8:
        raise FantasyServiceError("Tu possèdes déjà les 8 joueurs autorisés.")
    if candidate_type == "team" and team_rows:
        raise FantasyServiceError("Tu as déjà drafté une équipe professionnelle.")

    player_roles = {str(row.role) for row in player_rows}
    player_competitions = {
        str(row.player_competition)
        for row in player_rows
        if row.player_competition is not None
    }
    has_team = bool(team_rows)

    if candidate_type == "player":
        player_roles.add(str(candidate_role))
        player_competitions.add(str(candidate_competition))
    else:
        has_team = True

    missing = {role.value for role in PlayerRole if role.value not in player_roles}
    if not has_team:
        missing.add("TEAM")

    future_picks = remaining_picks_for_manager(
        manager_ids, manager_id, completed_picks=overall_pick, rounds=ROUNDS
    )
    if not can_still_complete_roster(missing, future_picks):
        raise FantasyServiceError(
            "Ce pick rendrait impossible la constitution d'un roster complet."
        )

    future_player_picks = future_picks - (0 if has_team else 1)
    if len(player_competitions) < 2 and future_player_picks <= 0:
        raise FantasyServiceError(
            "Tes 8 joueurs doivent représenter au moins deux championnats."
        )


def _materialize_rosters(connection: Connection, season_id: int, draft_id: int) -> None:
    managers = connection.execute(
        text(
            """
            SELECT m.id
            FROM fantasy.manager m
            JOIN fantasy.season s ON s.league_id = m.league_id
            WHERE s.id = :season_id
            ORDER BY m.draft_position
            """
        ),
        {"season_id": season_id},
    ).all()

    for manager in managers:
        rows = connection.execute(
            text(
                """
                SELECT
                    dp.overall_pick,
                    p.id AS player_id,
                    p.handle,
                    p.role,
                    player_team.competition_code AS player_competition,
                    team.id AS team_id,
                    team.name AS team_name,
                    team.competition_code AS team_competition
                FROM fantasy.draft_pick dp
                LEFT JOIN fantasy.pro_player p ON p.id = dp.player_id
                LEFT JOIN LATERAL (
                    SELECT current_team.competition_code
                    FROM fantasy.pro_player_team_history history
                    JOIN fantasy.pro_team current_team ON current_team.id = history.team_id
                    WHERE history.player_id = dp.player_id
                      AND history.valid_from <= NOW()
                      AND (history.valid_until IS NULL OR history.valid_until > NOW())
                    ORDER BY history.valid_from DESC
                    LIMIT 1
                ) player_team ON TRUE
                LEFT JOIN fantasy.pro_team team ON team.id = dp.team_id
                WHERE dp.draft_id = :draft_id AND dp.manager_id = :manager_id
                ORDER BY dp.overall_pick
                """
            ),
            {"draft_id": draft_id, "manager_id": int(manager.id)},
        ).all()

        players: list[PlayerAsset] = []
        team_asset: Optional[TeamAsset] = None
        for row in rows:
            if row.player_id is not None:
                if row.player_competition is None:
                    raise FantasyServiceError(
                        f"Le joueur {row.handle} n'a plus d'équipe active au moment de finaliser le draft."
                    )
                players.append(
                    PlayerAsset(
                        player_id=int(row.player_id),
                        handle=str(row.handle),
                        role=PlayerRole(str(row.role)),
                        competition=Competition(str(row.player_competition)),
                    )
                )
            elif row.team_id is not None:
                team_asset = TeamAsset(
                    team_id=int(row.team_id),
                    name=str(row.team_name),
                    competition=Competition(str(row.team_competition)),
                )

        if team_asset is None:
            raise FantasyServiceError("Un manager n'a pas drafté d'équipe professionnelle.")
        try:
            roster = choose_initial_roster(players, team_asset)
        except RosterValidationError as exc:
            raise FantasyServiceError(str(exc)) from exc

        for entry in roster:
            player_id = entry.player.player_id if entry.player is not None else None
            team_id = entry.team.team_id if entry.team is not None else None
            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.roster_asset
                        (season_id, manager_id, player_id, team_id, slot)
                    VALUES
                        (:season_id, :manager_id, :player_id, :team_id, :slot)
                    """
                ),
                {
                    "season_id": season_id,
                    "manager_id": int(manager.id),
                    "player_id": player_id,
                    "team_id": team_id,
                    "slot": entry.slot.value,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.roster_history
                        (season_id, manager_id, player_id, team_id, slot, valid_from, reason)
                    VALUES
                        (:season_id, :manager_id, :player_id, :team_id, :slot, NOW(), 'draft')
                    """
                ),
                {
                    "season_id": season_id,
                    "manager_id": int(manager.id),
                    "player_id": player_id,
                    "team_id": team_id,
                    "slot": entry.slot.value,
                },
            )


def pick_asset(
    *,
    league_id: int,
    guild_id: int,
    discord_user_id: int,
    asset_type: str,
    asset_name: str,
) -> PickResult:
    asset_type = str(asset_type).lower().strip()
    if asset_type not in {"player", "team"}:
        raise FantasyServiceError("Le type d'asset doit être `player` ou `team`.")
    asset_name = _clean_name(asset_name, "Le nom de l'asset", max_length=100)

    try:
        with transaction() as connection:
            league = _league_row(connection, league_id, guild_id, for_update=True)
            if league.status != "draft":
                raise FantasyServiceError("Aucun draft n'est actuellement actif pour cette Fantasy.")

            season = _current_season_row(connection, league_id)
            draft = connection.execute(
                text(
                    """
                    SELECT id, status, rounds
                    FROM fantasy.draft
                    WHERE season_id = :season_id
                    FOR UPDATE
                    """
                ),
                {"season_id": int(season.id)},
            ).first()
            if draft is None or draft.status != "active":
                raise FantasyServiceError("Le draft n'est pas actif.")

            managers = _manager_views(_manager_rows(connection, league_id))
            ordered_managers = [
                manager for manager in managers if manager.draft_position is not None
            ]
            ordered_managers.sort(key=lambda manager: int(manager.draft_position))
            manager_ids = [manager.manager_id for manager in ordered_managers]
            if len(manager_ids) < 2:
                raise FantasyServiceError("Ordre de draft invalide.")

            completed_picks = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM fantasy.draft_pick WHERE draft_id = :draft_id"),
                    {"draft_id": int(draft.id)},
                ).scalar_one()
            )
            total_picks = len(manager_ids) * ROUNDS
            if completed_picks >= total_picks:
                raise FantasyServiceError("Le draft est déjà terminé.")

            overall_pick = completed_picks + 1
            expected_manager_id = manager_for_pick(manager_ids, overall_pick, rounds=ROUNDS)
            expected_manager = next(
                manager for manager in ordered_managers if manager.manager_id == expected_manager_id
            )
            if int(expected_manager.discord_user_id) != int(discord_user_id):
                raise FantasyServiceError(
                    f"Ce n'est pas ton tour. Le pick #{overall_pick} appartient à "
                    f"<@{expected_manager.discord_user_id}>."
                )

            player_id = None
            team_id = None
            candidate_role = None
            if asset_type == "player":
                asset = _resolve_player(connection, asset_name)
                player_id = int(asset.id)
                candidate_role = str(asset.role)
                competition = str(asset.competition_code)
                already_picked = connection.execute(
                    text(
                        """
                        SELECT 1 FROM fantasy.draft_pick
                        WHERE draft_id = :draft_id AND player_id = :player_id
                        """
                    ),
                    {"draft_id": int(draft.id), "player_id": player_id},
                ).first()
                asset_display_name = str(asset.handle)
            else:
                asset = _resolve_team(connection, asset_name)
                team_id = int(asset.id)
                competition = str(asset.competition_code)
                already_picked = connection.execute(
                    text(
                        """
                        SELECT 1 FROM fantasy.draft_pick
                        WHERE draft_id = :draft_id AND team_id = :team_id
                        """
                    ),
                    {"draft_id": int(draft.id), "team_id": team_id},
                ).first()
                asset_display_name = str(asset.short_name or asset.name)

            if already_picked is not None:
                raise FantasyServiceError("Cet asset a déjà été drafté.")

            current_assets = _manager_pick_assets(
                connection, int(draft.id), expected_manager_id
            )
            _validate_candidate(
                manager_ids=manager_ids,
                manager_id=expected_manager_id,
                overall_pick=overall_pick,
                current_assets=current_assets,
                candidate_type=asset_type,
                candidate_role=candidate_role,
                candidate_competition=competition,
            )

            round_number = ((overall_pick - 1) // len(manager_ids)) + 1
            connection.execute(
                text(
                    """
                    INSERT INTO fantasy.draft_pick
                        (draft_id, overall_pick, round_number, manager_id, player_id, team_id)
                    VALUES
                        (:draft_id, :overall_pick, :round_number, :manager_id, :player_id, :team_id)
                    """
                ),
                {
                    "draft_id": int(draft.id),
                    "overall_pick": overall_pick,
                    "round_number": round_number,
                    "manager_id": expected_manager_id,
                    "player_id": player_id,
                    "team_id": team_id,
                },
            )

            draft_completed = overall_pick == total_picks
            if draft_completed:
                _materialize_rosters(connection, int(season.id), int(draft.id))
                connection.execute(
                    text(
                        """
                        UPDATE fantasy.draft
                        SET status = 'completed', completed_at = NOW()
                        WHERE id = :draft_id
                        """
                    ),
                    {"draft_id": int(draft.id)},
                )
                connection.execute(
                    text("UPDATE fantasy.league SET status = 'active' WHERE id = :league_id"),
                    {"league_id": league_id},
                )
                connection.execute(
                    text(
                        """
                        UPDATE fantasy.season
                        SET starts_at = COALESCE(starts_at, NOW())
                        WHERE id = :season_id
                        """
                    ),
                    {"season_id": int(season.id)},
                )

            pick_view = PickView(
                overall_pick=overall_pick,
                round_number=round_number,
                manager_id=expected_manager_id,
                discord_user_id=int(expected_manager.discord_user_id),
                asset_type=asset_type,
                asset_name=asset_display_name,
            )
    except IntegrityError as exc:
        raise FantasyServiceError(
            "Ce pick n'a pas pu être enregistré, probablement car l'asset vient d'être sélectionné."
        ) from exc

    return PickResult(pick=pick_view, draft_completed=draft_completed)


def get_draft_board(*, league_id: int, guild_id: int) -> DraftBoardView:
    with get_engine().connect() as connection:
        league_row = _league_row(connection, league_id, guild_id)
        season = _current_season_row(connection, league_id)
        manager_rows = _manager_rows(connection, league_id)
        managers = _manager_views(manager_rows)
        league = LeagueView(
            league_id=int(league_row.id),
            name=str(league_row.name),
            status=str(league_row.status),
            owner_discord_id=int(league_row.owner_discord_id),
            scoring_mode=str(league_row.scoring_mode),
            max_managers=int(league_row.max_managers),
            season_id=int(season.id),
            season_name=str(season.name),
            managers=managers,
        )

        draft = connection.execute(
            text(
                """
                SELECT id, status
                FROM fantasy.draft
                WHERE season_id = :season_id
                """
            ),
            {"season_id": int(season.id)},
        ).first()
        if draft is None:
            return DraftBoardView(
                league=league,
                draft_id=None,
                draft_status="pending",
                total_picks=len(managers) * ROUNDS,
                completed_picks=0,
                next_manager=None,
                picks=(),
            )

        rows = connection.execute(
            text(
                """
                SELECT
                    dp.overall_pick,
                    dp.round_number,
                    dp.manager_id,
                    m.discord_user_id,
                    CASE WHEN dp.player_id IS NOT NULL THEN 'player' ELSE 'team' END AS asset_type,
                    COALESCE(p.handle, team.short_name, team.name) AS asset_name
                FROM fantasy.draft_pick dp
                JOIN fantasy.manager m ON m.id = dp.manager_id
                LEFT JOIN fantasy.pro_player p ON p.id = dp.player_id
                LEFT JOIN fantasy.pro_team team ON team.id = dp.team_id
                WHERE dp.draft_id = :draft_id
                ORDER BY dp.overall_pick
                """
            ),
            {"draft_id": int(draft.id)},
        ).all()
        picks = tuple(
            PickView(
                overall_pick=int(row.overall_pick),
                round_number=int(row.round_number),
                manager_id=int(row.manager_id),
                discord_user_id=int(row.discord_user_id),
                asset_type=str(row.asset_type),
                asset_name=str(row.asset_name),
            )
            for row in rows
        )

        ordered_managers = [m for m in managers if m.draft_position is not None]
        ordered_managers.sort(key=lambda manager: int(manager.draft_position))
        total_picks = len(ordered_managers) * ROUNDS
        next_manager = None
        if draft.status == "active" and len(picks) < total_picks and ordered_managers:
            next_manager_id = manager_for_pick(
                [manager.manager_id for manager in ordered_managers],
                len(picks) + 1,
                rounds=ROUNDS,
            )
            next_manager = next(
                manager for manager in ordered_managers if manager.manager_id == next_manager_id
            )

        return DraftBoardView(
            league=league,
            draft_id=int(draft.id),
            draft_status=str(draft.status),
            total_picks=total_picks,
            completed_picks=len(picks),
            next_manager=next_manager,
            picks=picks,
        )
