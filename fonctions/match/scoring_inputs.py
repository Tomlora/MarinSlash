"""Identity, duration and timeline inputs shared by every scoring entry point."""


def game_minutes(match):
    """Riot duration is seconds; thisTime is a legacy MM.SS display value."""
    duration = getattr(match, 'match_detail', {}).get('info', {}).get('gameDuration')
    if duration is not None:
        return max(float(duration) / 60, 1 / 60)
    displayed = float(getattr(match, 'thisTime', 25))
    return max(int(displayed) + round((displayed % 1) * 100) / 60, 1 / 60)


def participant_indices(match):
    """Map Riot participant IDs to the display order, never to team colour."""
    ids = getattr(match, 'thisParticipantIdListe', [])
    if ids:
        return {int(pid): i for i, pid in enumerate(ids)}
    participants = getattr(match, 'match_detail', {}).get('info', {}).get('participants', [])
    puuids = {p: i for i, p in enumerate(getattr(match, 'thisPuuidListe', [])) if p}
    return {int(p['participantId']): puuids[p['puuid']] for p in participants
            if p.get('participantId') and p.get('puuid') in puuids}


def tracked_index(match):
    puuids = getattr(match, 'thisPuuidListe', [])
    if getattr(match, 'puuid', None) in puuids:
        return puuids.index(match.puuid)
    return match.thisId - 5 if match.thisId > 4 else match.thisId


def storage_index(match, local_index):
    """A shared match row must keep the same key from either tracked team."""
    ids = getattr(match, 'thisParticipantIdListe', [])
    return ids[local_index] - 1 if local_index < len(ids) else local_index


def extract_early_game(match):
    """Extract once per calculation, distinguishing absent @15 data from zero."""
    count = len(getattr(match, 'thisKillsListe', []))
    for name in ('thisGoldAt15Liste', 'thisCsAt15Liste', 'thisXpAt15Liste', 'thisSoloKillsListe', 'thisEarlySoloKillsListe'):
        setattr(match, name, [0] * count)
    match.thisEarlyGoldAvailableListe = [False] * count
    match.thisEarlyCsAvailableListe = [False] * count
    match.firstBloodKillIndex = match.firstTowerKillIndex = -1
    match.firstBloodAssistIndices = []
    match.firstTowerAssistIndices = []
    timeline = getattr(match, 'data_timeline', None)
    frames = timeline.get('info', {}).get('frames', []) if isinstance(timeline, dict) else []
    mapping = participant_indices(match)
    match.scoring_timeline_available = bool(frames and mapping)
    # A later frame or a shortened game's final frame is not an observation @15.
    frame_15 = next((f for f in frames if 900000 <= f.get('timestamp', 0) <= 905000), None)
    if frame_15:
        for pid, data in frame_15.get('participantFrames', {}).items():
            index = mapping.get(int(pid))
            if index is None:
                continue
            for key, target in (('totalGold', 'thisGoldAt15Liste'), ('xp', 'thisXpAt15Liste')):
                getattr(match, target)[index] = data.get(key, 0)
            match.thisCsAt15Liste[index] = data.get('minionsKilled', 0) + data.get('jungleMinionsKilled', 0)
            match.thisEarlyGoldAvailableListe[index] = 'totalGold' in data
            match.thisEarlyCsAvailableListe[index] = 'minionsKilled' in data and 'jungleMinionsKilled' in data
    first_blood_seen = first_tower_seen = False
    for frame in frames:
        for event in frame.get('events', []):
            kind = event.get('type')
            killer = mapping.get(event.get('killerId'))
            assists = sorted({mapping[p] for p in (event.get('assistingParticipantIds') or []) if p in mapping})
            if kind == 'CHAMPION_KILL':
                if not first_blood_seen:
                    first_blood_seen = True  # An execution must not credit a later kill.
                    match.firstBloodKillIndex = killer if killer is not None else -1
                    match.firstBloodAssistIndices = assists
                if killer is not None and not assists:
                    match.thisSoloKillsListe[killer] += 1
                    if event.get('timestamp', frame.get('timestamp', 0)) <= 900000:
                        match.thisEarlySoloKillsListe[killer] += 1
            elif kind == 'BUILDING_KILL' and event.get('buildingType') == 'TOWER_BUILDING' and not first_tower_seen:
                first_tower_seen = True
                match.firstTowerKillIndex = killer if killer is not None else -1
                match.firstTowerAssistIndices = assists
