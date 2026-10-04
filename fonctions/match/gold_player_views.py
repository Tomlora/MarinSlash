"""Or individuel sauvegardé et graphiques par poste/joueur du récap."""
import logging
from io import BytesIO

from .map_view import finite

ROLES = ("TOP", "JUNGLE", "MID", "ADC", "SUPP")
ALIASES = {"TOP": "TOP", "JUNGLE": "JUNGLE", "MIDDLE": "MID", "MID": "MID",
           "BOTTOM": "ADC", "BOT": "ADC", "UTILITY": "SUPP", "SUPPORT": "SUPP"}
BLUE, RED, MUTED = "#2563eb", "#dc2626", "#64748b"
log = logging.getLogger(__name__)


def build_snapshot(detail, timeline, puuid):
    info = detail.get("info", {}) if detail is not None else {}
    participants = info.get("participants") or []
    if len(participants) != 10 or {p.get("participantId") for p in participants} != set(range(1, 11)):
        return None
    if sorted(p.get("teamId", 0) for p in participants) != [100] * 5 + [200] * 5:
        return None
    frames = timeline.get("info", {}).get("frames", []) if isinstance(timeline, dict) else timeline
    if not frames:
        return None
    values = {pid: {} for pid in range(1, 11)}
    for frame in frames:
        stamp = finite(frame.get("timestamp"))
        if stamp is None or stamp < 0:
            continue
        minute = int(stamp // 60000)
        drift = stamp - minute * 60000
        if drift > 1000:
            continue
        samples = frame.get("participantFrames") or {}
        for pid, points in values.items():
            sample = samples.get(str(pid), samples.get(pid)) or {}
            gold = finite(sample.get("totalGold"))
            if gold is not None and gold >= 0 and (minute not in points or drift < points[minute][0]):
                points[minute] = (drift, gold)
    players = []
    for p in sorted(participants, key=lambda p: p["participantId"]):
        pid = p["participantId"]
        role = ALIASES.get(p.get("teamPosition")) or ALIASES.get(p.get("individualPosition"))
        players.append({"id": pid, "team": p["teamId"], "role": role,
                        "name": str(p.get("riotIdGameName") or p.get("summonerName") or "Joueur")[:60],
                        "champion": str(p.get("championName") or "Champion inconnu")[:40],
                        "points": [[m, values[pid][m][1]] for m in sorted(values[pid])]})
    tracked = next((p["teamId"] for p in participants if puuid and p.get("puuid") == puuid), None)
    return {"version": 1, "tracked_team": tracked, "players": players}


def snapshot_for_match(match):
    try:
        return build_snapshot(getattr(match, "match_detail", None),
                              getattr(match, "data_timeline", {}), getattr(match, "puuid", None))
    except (TypeError, ValueError, AttributeError, KeyError):
        log.exception("Or individuel indisponible pour %s", getattr(match, "last_match", "?"))
        return None


def ordered_players(data, team):
    return sorted((p for p in data["players"] if p["team"] == team),
                  key=lambda p: (ROLES.index(p["role"]) if p["role"] in ROLES else 5, p["id"]))


def role_series(data, team):
    """Soustraire uniquement deux joueurs de même poste et de même minute."""
    result = []
    for role in ROLES:
        sides = [[p for p in data["players"] if p["team"] == side and p["role"] == role]
                 for side in (team, 300 - team)]
        if any(len(players) != 1 for players in sides):
            result.append((role, None, None, []))
            continue
        ally, enemy = sides[0][0], sides[1][0]
        a, b = dict(ally["points"]), dict(enemy["points"])
        result.append((role, ally, enemy, [(m, a[m] - b[m]) for m in sorted(a.keys() & b.keys())]))
    return result


def with_gaps(points):
    """NaN coupe le trait aux minutes absentes sans inventer de valeur."""
    if not points:
        return [], []
    values = dict(points)
    minutes = list(range(int(min(values)), int(max(values)) + 1))
    return minutes, [values.get(m, float("nan")) for m in minutes]


def label(player):
    def clean(value, limit):
        value = str(value).replace("\n", " ").replace("\r", " ")
        return value if len(value) <= limit else value[:limit - 1] + "…"
    return f"{clean(player['champion'], 20)} · {clean(player['name'], 25)}"


def _figure(rows, cols, title, subtitle):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.ticker import MaxNLocator, FuncFormatter

    fig = Figure(figsize=(13 if cols == 1 else 16, 14), dpi=130, facecolor="white")
    FigureCanvasAgg(fig)
    axes = fig.subplots(rows, cols, squeeze=False)
    fig.suptitle(title, fontsize=22, color="#0f172a", y=.985, weight="bold")
    fig.text(.5, .956, subtitle, ha="center", fontsize=12, color="#475569")
    for ax in axes.flat:
        ax.set_facecolor("#f8fafc")
        ax.grid(True, color="#cbd5e1", alpha=.6)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=8, integer=True))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda n, _: f"{n / 1000:g} k" if n else "0"))
        ax.tick_params(labelsize=11, colors="#475569")
        for spine in ax.spines.values():
            spine.set_color("#cbd5e1")
    fig.subplots_adjust(left=.085, right=.96, bottom=.06, top=.91, hspace=.9, wspace=.23)
    return fig, axes


def _png(fig):
    output = BytesIO()
    fig.savefig(output, format="png", facecolor="white")
    return output.getvalue()


def render_roles(data, team, gold_segments):
    from matplotlib.collections import LineCollection
    # Réutiliser seulement la coloration et la gestion des trous du graphique historique.
    series = role_series(data, team)
    all_points = [point for _, _, _, points in series for point in points]
    if not all_points:
        return None
    peak = max(500, max(abs(v) for _, v in all_points) * 1.3)
    end = max(m for m, _ in all_points)
    fig, axes = _figure(5, 1, "Écart d'or par poste",
                        "Or allié − or adverse  |  Bleu : avantage allié · Rouge : avantage adverse  |  Même échelle partout")
    for ax, (role, ally, enemy, points) in zip(axes.flat, series):
        ax.set_title(role, loc="left", fontsize=14, weight="bold", pad=29)
        text = (f"Allié : {label(ally)}    /    Adversaire : {label(enemy)}" if ally else
                "Poste absent ou ambigu : comparaison indisponible")
        ax.text(0, 1.065, text, transform=ax.transAxes, fontsize=11, color="#475569", parse_math=False)
        ax.axhline(0, color=MUTED, linewidth=1)
        ax.set_xlim(-.5, max(1, end) + max(1, end * .025))
        ax.set_ylim(-peak, peak)
        if points:
            segments, colors = gold_segments(points)
            ax.add_collection(LineCollection(segments, colors=colors, linewidths=2.4))
            ax.scatter([m for m, _ in points], [v for _, v in points], s=12,
                       c=[BLUE if v > 0 else RED if v < 0 else MUTED for _, v in points], zorder=3)
            minute, value = points[-1]
            ax.text(1, 1.22, f"{minute}:00 · {value:+,.0f} or".replace(",", " "),
                    transform=ax.transAxes, ha="right", fontsize=12, weight="bold", color=BLUE if value >= 0 else RED)
        else:
            ax.text(.5, .5, "Aucune minute comparable", transform=ax.transAxes, ha="center", color=MUTED)
    axes[-1, 0].set_xlabel("Minute de jeu", fontsize=12)
    return _png(fig)


def render_players(data, team):
    points = [point for p in data["players"] for point in p["points"]]
    if not points:
        return None
    end = max(m for m, _ in points)
    peak = max(1000, max(v for _, v in points) * 1.15)
    fig, axes = _figure(5, 2, "Courbes d'or des 10 joueurs",
                        "ALLIÉS à gauche · ADVERSAIRES à droite  |  Une courbe par joueur · Échelles communes")
    for col, side in enumerate((team, 300 - team)):
        color = BLUE if col == 0 else RED
        for ax, player in zip(axes[:, col], ordered_players(data, side)):
            ax.set_title(f"{player['role'] or '?'} · {label(player)}", loc="left", fontsize=12,
                         weight="bold", pad=11, color=color, parse_math=False)
            ax.set_xlim(-.5, max(1, end) + max(1, end * .025))
            ax.set_ylim(0, peak)
            x, y = with_gaps(player["points"])
            if x:
                ax.plot(x, y, color=color, linewidth=2.3, marker=".", markersize=4)
                minute, value = player["points"][-1]
                ax.text(.025, .89, f"{minute}:00 · {value:,.0f} or".replace(",", " "),
                        transform=ax.transAxes, fontsize=11, color=color, weight="bold")
            else:
                ax.text(.5, .5, "Or non enregistré", transform=ax.transAxes, ha="center", color=MUTED)
        axes[-1, col].set_xlabel("Minute de jeu", fontsize=12)
    return _png(fig)
