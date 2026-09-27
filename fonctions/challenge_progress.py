"""Calculs des défis Riot, indépendants de Discord, SQL et du réseau."""
import math
import re

TIERS = ('NONE', 'IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'DIAMOND',
         'MASTER', 'GRANDMASTER', 'CHALLENGER')
TIER_NAMES = dict(zip(TIERS, ('Non classé', 'Fer', 'Bronze', 'Argent', 'Or',
    'Platine', 'Diamant', 'Maître', 'Grand maître', 'Challenger')))


def number(value, default=0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def clean(value, limit=200):
    value = re.sub(r'<[^>]+>', '', str(value or ''))
    value = re.sub(r'[@*`~|\\]', '', value)
    return ' '.join(value.split())[:limit]


def normalize(player, config, observed_at):
    """Ne jamais transformer une réponse d'erreur Riot en remise à zéro."""
    if not isinstance(player, dict) or not isinstance(player.get('challenges'), list):
        raise ValueError('Réponse challenges Riot invalide')
    if not isinstance(player.get('totalPoints'), dict) or not isinstance(config, list):
        raise ValueError('Configuration challenges Riot invalide')
    definitions = {int(c['id']): c for c in config if 'id' in c}
    entries = {}
    for raw in player['challenges']:
        cid = int(raw['challengeId'])
        definition = definitions.get(cid, {})
        localized = definition.get('localizedNames', {})
        names = localized.get('fr_FR') or localized.get('en_US') or {}
        level = raw.get('level', 'NONE')
        # Conserver l'état Riot et les seuils avec chaque relevé historique.
        entries[str(cid)] = {
            'id': cid, 'name': clean(names.get('name') or f'Défi {cid}', 100),
            'description': clean(names.get('shortDescription') or names.get('description'), 240),
            'level': level if level in TIERS else 'NONE',
            'value': number(raw.get('value')), 'position': max(0, number(raw.get('position'))),
            'percentile': number(raw.get('percentile'), None),
            'state': definition.get('state', 'UNKNOWN'),
            'thresholds': {tier: number(value) for tier, value in definition.get('thresholds', {}).items()
                           if tier in TIERS and number(value, None) is not None},
            # Les IDs inférieurs à 10000 sont les cristaux/catégories Riot.
            'aggregate': cid < 10000,
        }
    return {'version': 1, 'observed_at': observed_at, 'entries': list(entries.values()),
            'total': player['totalPoints'], 'categories': player.get('categoryPoints', {})}


def next_goal(entry):
    """Seuils explicites, y compris NONE, sans inventer de palier absent."""
    current = TIERS.index(entry['level'])
    for tier in TIERS[current + 1:]:
        target = entry.get('thresholds', {}).get(tier)
        if target is not None and target > entry['value']:
            lower = entry.get('thresholds', {}).get(entry['level'], 0)
            span = target - lower
            return {'tier': tier, 'target': target, 'remaining': target - entry['value'],
                    'ratio': min(1, max(0, (entry['value'] - lower) / span)) if span > 0 else 0}
    return None


def visible(entries, preferences):
    excluded = set(preferences.get('excluded', []))
    return [e for e in entries if not e.get('aggregate') and e['id'] not in excluded]


def objectives(entries, preferences, limit=5):
    favorites = set(preferences.get('favorites', []))
    goals = []
    for entry in visible(entries, preferences):
        if entry.get('state') != 'ENABLED':
            continue
        goal = next_goal(entry)
        if goal:
            goals.append(dict(entry, goal=goal, favorite=entry['id'] in favorites))
    return sorted(goals, key=lambda e: (not e['favorite'], -e['goal']['ratio'], e['id']))[:limit]


def compare(previous, current, preferences):
    old = {e['id']: e for e in (previous or {}).get('entries', [])}
    changes = []
    favorites = set(preferences.get('favorites', []))
    for entry in visible(current['entries'], preferences):
        before = old.get(entry['id'])
        if before is None:
            # Un nouveau défi n'a pas de valeur de référence comparable.
            continue
        delta = entry['value'] - before['value']
        level_delta = TIERS.index(entry['level']) - TIERS.index(before['level'])
        rank_delta = before['position'] - entry['position'] if before['position'] > 0 and entry['position'] > 0 else 0
        if delta or level_delta or rank_delta:
            changes.append(dict(entry, delta=delta, before=before['value'],
                old_level=before['level'], level_delta=level_delta, rank_delta=rank_delta,
                goal=next_goal(entry), favorite=entry['id'] in favorites))
    changes.sort(key=lambda e: (e['level_delta'] <= 0, not e['favorite'],
                                -(e['goal']['ratio'] if e['goal'] else 0), e['id']))
    return {'version': 1, 'observed_at': current['observed_at'],
            'since': previous['observed_at'] if previous else None,
            'baseline': previous is None, 'total': current['total'],
            'points_delta': number(current['total'].get('current')) - number(previous['total'].get('current')) if previous else None,
            'changes': changes, 'goals': objectives(current['entries'], preferences)}
