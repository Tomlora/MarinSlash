"""Filtres du récap, sans accès réseau ni connexion à la base au chargement."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re


DURATION_DAYS = {'24h': 1, '48h': 2, '72h': 3, '96h': 4, 'Semaine': 7, 'Mois': 30}
GAME_COUNTS = tuple(range(10, 101, 10))


def normalize_champion(champion):
    return re.sub(r'[^a-z0-9]', '', (champion or '').lower())


def recap_query(riot_id, riot_tag, mode=None, observation=None,
                observation_parties=None, champion=None, now=None):
    """Filtrer, dédupliquer les matchs, puis limiter avant la jointure des prédictions."""
    if observation is not None and observation_parties is not None:
        raise ValueError("Choisis une durée OU un nombre de parties, pas les deux.")
    if observation_parties is not None and observation_parties not in GAME_COUNTS:
        raise ValueError("Choisis entre 10 et 100 parties, par pas de 10.")
    if observation_parties is None:
        observation = observation or '24h'
        if observation not in (*DURATION_DAYS, 'today'):
            raise ValueError("Durée d'observation inconnue.")

    params = {'riot_id': riot_id.lower().replace(' ', ''), 'riot_tag': riot_tag.upper()}
    filters = ['tracker.riot_id = :riot_id', 'tracker.riot_tagline = :riot_tag']
    if mode:
        filters.append('matchs.mode = :mode')
        params['mode'] = mode
    if champion is not None:
        normalized = normalize_champion(champion)
        if not normalized:
            raise ValueError('Précise un nom de champion.')
        filters.append("REGEXP_REPLACE(LOWER(matchs.champion), '[^a-z0-9]', '', 'g') = :champion")
        params['champion'] = normalized

    if observation_parties is not None:
        label = f'{observation_parties} dernières parties'
        params['limit'] = observation_parties
        limit = 'LIMIT :limit'
    else:
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        limit = ''
        if observation == 'today':
            start = now.astimezone(ZoneInfo('Europe/Paris')).replace(
                hour=0, minute=0, second=0, microsecond=0)
            label = "Aujourd'hui"
        else:
            # Les durées glissantes restent exactes lors des changements d'heure.
            start = now.astimezone(timezone.utc) - timedelta(days=DURATION_DAYS[observation])
            label = observation
        filters.extend(['matchs.datetime >= :date_start', 'matchs.datetime <= :date_end'])
        params.update(date_start=start.astimezone(timezone.utc), date_end=now.astimezone(timezone.utc))

    if champion:
        label += f' · Champion : {champion}'
    if mode:
        label += f' · {mode}'

    sql = f'''WITH ranked_matches AS (
        SELECT matchs.*, tracker.riot_id, tracker.riot_tagline,
               ROW_NUMBER() OVER (
                   PARTITION BY matchs.match_id
                   ORDER BY matchs.datetime DESC, matchs.id DESC
               ) AS recap_row
        FROM matchs
        INNER JOIN tracker ON tracker.id_compte = matchs.joueur
        WHERE {' AND '.join(filters)}
    ), selected_matches AS (
        SELECT * FROM ranked_matches WHERE recap_row = 1
        ORDER BY datetime DESC, id DESC
        {limit}
    )
    SELECT matchs.id, matchs.match_id, prev_lol.win AS proba1, prev_lol.lose AS proba2,
           prev_lol.team, prev_lol.victory_predicted, matchs.champion, id_participant,
           mvp, time, kills, deaths, assists, quadra, penta, tier, rank, mode, kp, kda,
           victoire, ecart_lp, ecart_gold, solokills, datetime
    FROM selected_matches AS matchs
    LEFT JOIN prev_lol ON matchs.riot_id = prev_lol.riot_id
        AND matchs.riot_tagline = prev_lol.riot_tag AND matchs.match_id = prev_lol.match_id
    ORDER BY matchs.datetime DESC, matchs.id DESC'''
    return sql, params, label
