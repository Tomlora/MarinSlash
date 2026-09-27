"""Persistance atomique des relevés et des évolutions associées aux récaps."""
import json
import threading
from sqlalchemy import text

from fonctions.challenge_progress import compare

SCHEMA = (
    '''CREATE TABLE IF NOT EXISTS challenge_accounts (
        joueur BIGINT PRIMARY KEY, data JSONB NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS match_challenges (
        match_id VARCHAR(40) NOT NULL, joueur BIGINT NOT NULL, data JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (match_id, joueur))''',
    '''CREATE TABLE IF NOT EXISTS challenge_preferences (
        joueur BIGINT NOT NULL, challenge_id BIGINT NOT NULL,
        favorite BOOLEAN NOT NULL DEFAULT FALSE, excluded BOOLEAN NOT NULL DEFAULT FALSE,
        PRIMARY KEY (joueur, challenge_id))''',
    'CREATE INDEX IF NOT EXISTS match_challenges_history ON match_challenges (joueur, created_at DESC)',
)
_ready = False
_schema_lock = threading.Lock()


def engine():
    # Import tardif : les calculs et le rendu fonctionnent sans configuration SQL.
    from fonctions.gestion_bdd import engine as database
    return database


def ensure_schema():
    global _ready
    with _schema_lock:
        if _ready:
            return
        with engine().begin() as conn:
            # Sérialiser aussi les migrations entre plusieurs processus du bot.
            conn.execute(text('SELECT pg_advisory_xact_lock(736214, 0)'))
            for statement in SCHEMA:
                conn.execute(text(statement))
            if conn.execute(text("SELECT to_regclass('challenge_exclusion')")).scalar():
                conn.execute(text('''INSERT INTO challenge_preferences (joueur, challenge_id, excluded)
                    SELECT "index", "challengeId", TRUE FROM challenge_exclusion
                    ON CONFLICT DO NOTHING'''))
        _ready = True


def decode(value):
    return json.loads(value) if isinstance(value, str) else value


def _current(conn, joueur):
    return decode(conn.execute(text('SELECT data FROM challenge_accounts WHERE joueur=:joueur'),
                               {'joueur': int(joueur)}).scalar())


def _preferences(conn, joueur):
    rows = conn.execute(text('''SELECT challenge_id, favorite, excluded FROM challenge_preferences
        WHERE joueur IN (:joueur, -1)'''), {'joueur': int(joueur)}).mappings()
    result = {'favorites': [], 'excluded': []}
    for row in rows:
        if row['favorite']:
            result['favorites'].append(row['challenge_id'])
        if row['excluded']:
            result['excluded'].append(row['challenge_id'])
    return result


def profile(joueur):
    ensure_schema()
    with engine().connect() as conn:
        return _current(conn, joueur), _preferences(conn, joueur)


def load_match(match_id, joueur):
    ensure_schema()
    with engine().connect() as conn:
        return decode(conn.execute(text('''SELECT data FROM match_challenges
            WHERE match_id=:match_id AND joueur=:joueur'''),
            {'match_id': str(match_id), 'joueur': int(joueur)}).scalar())


def save_observation(joueur, current, match_id=None):
    """Baseline + détail dans une transaction; un match publié reste immuable."""
    ensure_schema()
    params = {'joueur': int(joueur), 'match_id': str(match_id)}
    with engine().begin() as conn:
        conn.execute(text('SELECT pg_advisory_xact_lock(736215, :joueur)'), {'joueur': int(joueur)})
        if match_id:
            existing = conn.execute(text('''SELECT data FROM match_challenges
                WHERE match_id=:match_id AND joueur=:joueur'''), params).scalar()
            if existing is not None:
                return decode(existing)
        previous = _current(conn, joueur)
        if previous and current['observed_at'] < previous['observed_at']:
            raise ValueError('Relevé plus ancien que la référence enregistrée')
        snapshot = compare(previous, current, _preferences(conn, joueur))
        if match_id:
            conn.execute(text('''INSERT INTO match_challenges (match_id, joueur, data)
                VALUES (:match_id, :joueur, CAST(:data AS JSONB))'''),
                dict(params, data=json.dumps(snapshot, ensure_ascii=False, allow_nan=False)))
        conn.execute(text('''INSERT INTO challenge_accounts (joueur, data)
            VALUES (:joueur, CAST(:data AS JSONB))
            ON CONFLICT (joueur) DO UPDATE SET data=EXCLUDED.data'''),
            dict(params, data=json.dumps(current, ensure_ascii=False, allow_nan=False)))
        return snapshot


def set_preference(joueur, challenge_id, action):
    changes = {'suivre': ('favorite', True), 'retirer': ('favorite', False),
               'exclure': ('excluded', True), 'inclure': ('excluded', False)}
    column, value = changes[action]  # Colonne issue uniquement de cette liste fermée.
    ensure_schema()
    with engine().begin() as conn:
        conn.execute(text(f'''INSERT INTO challenge_preferences (joueur, challenge_id, {column})
            VALUES (:joueur, :challenge_id, :value)
            ON CONFLICT (joueur, challenge_id) DO UPDATE SET {column}=EXCLUDED.{column}'''),
            {'joueur': int(joueur), 'challenge_id': int(challenge_id), 'value': value})
        # Vider l'ancienne exclusion afin qu'un redémarrage ne la réimporte pas.
        if action == 'inclure' and conn.execute(text("SELECT to_regclass('challenge_exclusion')")).scalar():
            conn.execute(text('''DELETE FROM challenge_exclusion
                WHERE "index"=:joueur AND "challengeId"=:cid'''),
                {'joueur': int(joueur), 'cid': int(challenge_id)})


def history(joueur, limit=10):
    ensure_schema()
    with engine().connect() as conn:
        return [(r.match_id, decode(r.data)) for r in conn.execute(text('''SELECT match_id, data
            FROM match_challenges WHERE joueur=:joueur ORDER BY created_at DESC LIMIT :limit'''),
            {'joueur': int(joueur), 'limit': int(limit)})]


def accounts(guild_id=None, daily=False):
    query = 'SELECT id_compte, riot_id, riot_tagline, puuid, discord, server_id, challenges FROM tracker WHERE banned=false'
    if guild_id is not None:
        query += ' AND server_id=:guild'
    if daily:
        query += ''' AND activation=true AND (challenges=false OR NOT EXISTS
            (SELECT 1 FROM challenge_accounts c WHERE c.joueur=tracker.id_compte))'''
    ensure_schema()
    with engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(query), {'guild': guild_id}).mappings()]


def leaderboard(guild_id):
    ensure_schema()
    with engine().connect() as conn:
        return [dict(r, data=decode(r['data'])) for r in conn.execute(text('''
            SELECT t.riot_id, t.riot_tagline, c.data FROM challenge_accounts c
            JOIN tracker t ON t.id_compte=c.joueur
            WHERE t.server_id=:guild AND t.banned=false
            ORDER BY CAST(c.data->'total'->>'current' AS NUMERIC) DESC LIMIT 20'''),
            {'guild': int(guild_id)}).mappings()]
