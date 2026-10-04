"""Profils du lobby capturés avant les filtres des insights, sans appel réseau."""
import logging
import math

log = logging.getLogger(__name__)
ROLES = {"top": "TOP", "jungle": "JUNGLE", "jgl": "JUNGLE", "mid": "MID",
         "middle": "MID", "adc": "ADC", "bottom": "ADC", "bot": "ADC",
         "support": "SUPPORT", "utility": "SUPPORT", "supp": "SUPPORT"}
ROLE_ORDER = {role: i for i, role in enumerate(("TOP", "JUNGLE", "MID", "ADC", "SUPPORT"))}


def count(value):
    try:
        n = float(value)
        return int(n) if math.isfinite(n) and n >= 0 and n.is_integer() else None
    except (TypeError, ValueError):
        return None


def results(stats):
    """Conserver des comptes exacts ; ne jamais les deviner depuis un WR arrondi."""
    if not isinstance(stats, dict):
        return None
    wins = count(stats.get("wins"))
    losses = count(stats.get("losses", stats.get("looses")))
    total = count(stats.get("totalMatches", stats.get("gamesCount")))
    if losses is None and wins is not None and total is not None and total >= wins:
        losses = total - wins
    if wins is None or losses is None or (total is not None and total != wins + losses):
        return None
    games = wins + losses
    return {"wins": wins, "losses": losses, "games": games,
            "winrate": round(100 * wins / games, 1) if games else None}


def normalized(value):
    return "".join(c for c in str(value or "").casefold() if c.isalnum())


def profile(match, index, source):
    # Ces listes sont réordonnées ensemble ; l'association persistante est le PUUID.
    puuids = getattr(match, "thisPuuidListe", [])
    if index >= len(puuids) or not puuids[index]:
        return None
    if not hasattr(match, "player_profiles_raw"):
        match.player_profiles_raw = {}
    item = match.player_profiles_raw.setdefault(puuids[index], {})
    item["source"] = source
    return item


def capture_global(match, index, stats, source):
    item = profile(match, index, source)
    if item is not None:
        item["global"] = results(stats)


def capture_champions(match, index, dataframe, source):
    item = profile(match, index, source)
    if item is None:
        return
    item["champion"] = None
    item["champion_share"] = None
    if not hasattr(dataframe, "to_dict") or dataframe.empty:
        return
    champion = normalized(match.thisChampNameListe[index])
    rows = [(normalized(r.get("championId")), results(r)) for r in dataframe.to_dict("records")]
    # Additionner les lignes du même champion (par rôle chez Mobalytics).
    selected = [r for name, r in rows if name == champion]
    if any(r is None for r in selected):
        return
    wins = sum(r["wins"] for r in selected)
    losses = sum(r["losses"] for r in selected)
    item["champion"] = results({"wins": wins, "losses": losses})
    if all(r is not None for _, r in rows):
        total = sum(r["games"] for _, r in rows)
        if total:
            item["champion_share"] = 100 * (wins + losses) / total


def capture_roles(match, index, data, source):
    item = profile(match, index, source)
    if item is None:
        return
    item["roles"] = None
    if hasattr(data, "to_dict"):
        rows = data.to_dict("records")
    elif isinstance(data, dict):
        rows = [{"role": role, **stats} for role, stats in data.items() if isinstance(stats, dict)]
    else:
        return
    counts = {}
    for row in rows:
        role = ROLES.get(str(row.get("role", "")).lower())
        games = count(row.get("nbgames", row.get("gameCount")))
        if role is None or games is None:
            # Un historique incomplet ne doit pas produire un faux pourcentage.
            return
        counts[role] = counts.get(role, 0) + games
    total = sum(counts.values())
    if total:
        main = max(counts, key=lambda role: (counts[role], -ROLE_ORDER[role]))
        item["roles"] = {"games": total, "main": main, "counts": counts,
                         "share": 100 * counts[main] / total}


def snapshot_players(match):
    """Rosters complets, même lorsque les fournisseurs ne renvoient aucun profil."""
    try:
        detail = getattr(match, "match_detail", {})
        players = detail.get("info", {}).get("participants", [])
        if len(players) != 10 or sorted(p.get("teamId", 0) for p in players) != [100] * 5 + [200] * 5:
            return None
        tracked = next((p for p in players if p.get("puuid") == getattr(match, "puuid", None)), None)
        if tracked is None:
            return None
        indices = {puuid: i for i, puuid in enumerate(getattr(match, "thisPuuidListe", []))}
        raw = getattr(match, "player_profiles_raw", {})
        saved = []
        for player in players:
            idx = indices.get(player.get("puuid"))
            def fallback(attr):
                values = getattr(match, attr, [])
                return values[idx] if idx is not None and idx < len(values) else ""
            data = raw.get(player.get("puuid"), {})
            role = ROLES.get(str(player.get("teamPosition") or player.get("individualPosition") or "").lower())
            saved.append({
                "id": player.get("participantId"), "team": player["teamId"],
                "name": str(player.get("riotIdGameName") or fallback("thisRiotIdListe") or "Joueur")[:60],
                "tag": str(player.get("riotIdTagline") or fallback("thisRiotTagListe"))[:20],
                "champion_name": str(player.get("championName") or fallback("thisChampNameListe") or "Champion inconnu")[:40],
                "role": role, "source": data.get("source"),
                "global": data.get("global"), "champion": data.get("champion"),
                "champion_share": data.get("champion_share"), "roles": data.get("roles"),
            })
        return {"version": 1, "allied_team": tracked["teamId"], "players": saved}
    except (TypeError, ValueError, AttributeError, KeyError):
        log.exception("Profils du lobby indisponibles pour %s", getattr(match, "last_match", "?"))
        return None


def percent(value):
    return f"{value:.1f}".rstrip("0").rstrip(".") + " %"


def winrate_text(stats):
    if stats is None:
        return "Données indisponibles"
    if not stats["games"]:
        return "Aucune partie (0 V / 0 D)"
    return f"**{percent(stats['winrate'])}** ({stats['wins']} V / {stats['losses']} D)"


def profile_text(player):
    lines = [f"**Winrate global · Solo/Duo :** {winrate_text(player['global'])}",
             f"**Sur ce champion :** {winrate_text(player['champion'])}"]
    roles, role = player.get("roles"), player.get("role")
    lines.append("**Rôle principal :** " + (f"{roles['main']} ({percent(roles['share'])})" if roles else "Données indisponibles"))
    lines.append(f"**Rôle joué :** {role or 'Indisponible'}")
    share, champion = player.get("champion_share"), player.get("champion")
    if share is not None and champion:
        otp = champion["games"] >= 20 and int(share) > 70
        lines.append(f"**OTP :** {'Détecté' if otp else 'Non détecté'} · {percent(share)} des parties sur ce champion")
    else:
        lines.append("**OTP :** Données insuffisantes")
    if roles and role:
        weight = 100 * roles["counts"].get(role, 0) / roles["games"]
        # Seuils des insights : <=15 % du rôle actuel et >30 parties de référence.
        threshold_weight = int(weight) if player.get("source") == "U.GG" else int(round(weight))
        status = ("Probable" if threshold_weight <= 15 else "Non détecté") if roles["games"] > 30 else "Historique insuffisant"
        lines.append(f"**Autofill :** {status} · {percent(weight)} en {role} ({roles['games']} parties analysées)")
    else:
        lines.append("**Autofill :** Données insuffisantes")
    return "\n".join(lines)


def build_player_pages(match, data):
    from .match_views import make_pages, _finish, _champion_icon
    if not data or data.get("version") != 1:
        return _finish(make_pages("👥 Caractéristiques des joueurs", match, [
            ("Profils indisponibles", "Ces caractéristiques n'ont pas été sauvegardées pour cet ancien récap.")]))
    pages = []
    for allied, title, color in ((True, "Alliés", 0x3498DB), (False, "Adversaires", 0xE74C3C)):
        roster = [p for p in data["players"] if (p["team"] == data["allied_team"]) == allied]
        roster.sort(key=lambda p: (ROLE_ORDER.get(p["role"], 5), p["id"] or 0))
        fields = []
        for player in roster:
            # Noms dans un champ, limités et sur une ligne pour garder les cinq fiches lisibles.
            name = " ".join(f"{player['name']}#{player['tag']}".split())
            fields.append((f"{_champion_icon(player['champion_name'])} {name} · {player['champion_name']}", profile_text(player)))
        sources = sorted({p['source'] for p in roster if p.get('source')})
        note = "Statistiques Solo/Duo disponibles au moment du récap · " + (", ".join(sources) or "Source indisponible")
        pages += make_pages("👥 Caractéristiques · " + title, match, fields, note, color)
    for i, page in enumerate(pages):
        page.set_footer(text=f"Page {i + 1}/{len(pages)} · OTP : ≥20 parties, >70 % du champion · Autofill : rôle ≤15 %, historique >30 parties (estimation)")
    return pages


def load_players(match_id, joueur):
    from .recap_details import load_details
    loaded = load_details(match_id, joueur)
    return None if loaded is None else (loaded[0], loaded[1].get("players"))
