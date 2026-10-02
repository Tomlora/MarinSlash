"""Carte du récap : snapshot des dix joueurs, sans requête Riot au clic."""
import logging
import math
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WINDOW_MS = 5 * 60_000
ALL_PLAYERS = 1023
log = logging.getLogger(__name__)


def finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def position(value):
    if not isinstance(value, dict):
        return None
    x, y = finite(value.get("x")), finite(value.get("y"))
    if x is None or y is None or not (0 <= x <= 15000 and 0 <= y <= 15000):
        return None
    # Riot utilise parfois l'origine pour une position inconnue.
    return [int(x), int(y)] if x or y else None


def build_map_snapshot(detail, timeline):
    """Identités Riot natives, jamais les index réordonnés du scoring."""
    info = (detail or {}).get("info", {})
    participants = info.get("participants") or []
    if info.get("mapId") != 11 or len(participants) != 10:
        return None
    if {p.get("participantId") for p in participants} != set(range(1, 11)):
        return None
    if sorted(p.get("teamId", 0) for p in participants) != [100] * 5 + [200] * 5:
        return None
    frames = timeline.get("info", {}).get("frames", []) if isinstance(timeline, dict) else []
    if not frames:
        return None
    players = [{"id": p["participantId"], "team": p["teamId"],
                "name": str(p.get("riotIdGameName") or p.get("summonerName") or "Joueur")[:60],
                "champion": str(p.get("championName") or "Champion inconnu")[:40]}
               for p in sorted(participants, key=lambda p: (p["teamId"], p["participantId"]))]
    samples, deaths, seen = {}, [], set()
    last = 0
    for frame in frames:
        stamp = finite(frame.get("timestamp"))
        if stamp is not None and stamp >= 0:
            last = max(last, int(stamp))
            for pid, sample in (frame.get("participantFrames") or {}).items():
                if str(pid) not in {str(i) for i in range(1, 11)}:
                    continue
                xy = position(sample.get("position"))
                if xy:
                    samples[(int(pid), int(stamp))] = [int(pid), int(stamp), *xy]
        # Inclure aussi les événements de la dernière frame partielle.
        for event in frame.get("events", []):
            if event.get("type") != "CHAMPION_KILL" or event.get("victimId") not in range(1, 11):
                continue
            stamp = finite(event.get("timestamp"))
            xy = position(event.get("position"))
            if stamp is None or stamp < 0:
                continue
            last = max(last, int(stamp))
            key = (event["victimId"], int(stamp))
            if key in seen:
                continue
            seen.add(key)
            deaths.append({"id": event["victimId"], "t": int(stamp), "xy": xy,
                           "killer": event.get("killerId", 0)})
    if not samples and not deaths:
        return None
    return {"version": 1, "players": players, "end": last,
            "positions": sorted(samples.values(), key=lambda s: (s[1], s[0])),
            "deaths": sorted(deaths, key=lambda d: (d["t"], d["id"]))}


def snapshot_for_match(match):
    # Ce complément optionnel ne doit pas faire perdre les scores ou l'or.
    try:
        return build_map_snapshot(getattr(match, "match_detail", {}), getattr(match, "data_timeline", {}))
    except (TypeError, ValueError, AttributeError, KeyError):
        log.exception("Snapshot de carte indisponible pour %s", getattr(match, "last_match", "?"))
        return None


def clock(stamp):
    seconds = int(stamp // 1000)
    return f"{seconds // 60:02}:{seconds % 60:02}"


def selection(data, mask):
    return [p for p in data["players"] if mask & (1 << (p["id"] - 1))]


def last_page(data):
    return max(0, (max(1, data["end"]) - 1) // WINDOW_MS)


def window(data, page):
    page = min(max(0, page), last_page(data))
    return page * WINDOW_MS, min((page + 1) * WINDOW_MS, data["end"])


def player_events(data, pid, page, mode):
    start, end = window(data, page)
    if mode == "moves":
        # Les relevés de frontière apparaissent dans les deux fenêtres voisines.
        return [{"t": t, "xy": [x, y]} for p, t, x, y in data["positions"]
                if p == pid and start <= t <= end]
    return [d for d in data["deaths"] if d["id"] == pid and start <= d["t"]
            and (d["t"] < end or (page == last_page(data) and d["t"] == end))]


def map_pixel(xy, size):
    return xy[0] / 15000 * (size - 1), (1 - xy[1] / 15000) * (size - 1)


def render_map(data, mode, page, mask):
    """Une carte par joueur : aucun entrelacement de dix trajectoires."""
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance

    players = selection(data, mask)
    count = len(players)
    if not count:
        raise ValueError("Sélection vide")
    cols, size = (1, 680) if count == 1 else ((2, 460) if count <= 4 else (5, 300))
    cols = min(cols, count)
    rows = math.ceil(count / cols)
    gap, header, card = 20, 102, size + 160
    canvas = Image.new("RGB", (cols * (size + gap) + gap, header + rows * card + 48), "#101827")
    draw = ImageDraw.Draw(canvas)
    font_path = str(ROOT / "utils/font/DejaVuSans.ttf")
    font = ImageFont.truetype(font_path, 19)
    small = ImageFont.truetype(font_path, 16)
    title = ImageFont.truetype(str(ROOT / "utils/font/DejaVuSans-Bold.ttf"), 27)

    def fit(text, width, face=font):
        while text and draw.textbbox((0, 0), text, font=face)[2] > width:
            text = text[:-2].rstrip() + "…"
        return text

    start, end = window(data, page)
    label = "MORTS" if mode == "deaths" else "DÉPLACEMENTS"
    draw.text((gap, 18), f"{label}  ·  {clock(start)} – {clock(end)}", font=title, fill="white")
    draw.text((gap, 59), f"{count} joueur(s) · Une carte par joueur · Sélectionne moins de joueurs pour agrandir", font=small, fill="#becbdd")
    with Image.open(ROOT / "img/map2.jpg") as asset:
        background = ImageEnhance.Brightness(asset.convert("RGB").resize((size, size))).enhance(0.57)
    for i, player in enumerate(players):
        x = gap + (i % cols) * (size + gap)
        y = header + (i // cols) * card
        blue = player["team"] == 100
        color = "#69c8ff" if blue else "#ff9a98"
        draw.text((x, y), fit(f"{player['id']:02} · {player['champion']}", size), font=font, fill=color)
        draw.text((x, y + 27), fit(player["name"], size, small), font=small, fill="#dce5f2")
        top = y + 56
        canvas.paste(background, (x, top))
        draw.rectangle((x, top, x + size - 1, top + size - 1), outline=color, width=2)
        events = player_events(data, player["id"], page, mode)
        plotted = [e for e in events if e["xy"]]
        occupied = []
        legends = []
        for n, event in enumerate(plotted, 1):
            px, py = map_pixel(event["xy"], size)
            px, py = x + px, top + py
            # Déplacer uniquement les étiquettes, en gardant un trait vers la vraie position.
            tx, ty = px, py
            for attempt in range(60):
                tx = max(x + 13, min(x + size - 14, tx))
                ty = max(top + 13, min(top + size - 14, ty))
                if all(math.hypot(tx - ox, ty - oy) >= 27 for ox, oy in occupied):
                    break
                angle = attempt * 2.4
                radius = 18 + attempt * 2
                tx, ty = px + math.cos(angle) * radius, py + math.sin(angle) * radius
            occupied.append((tx, ty))
            draw.line((px, py, tx, ty), fill=color, width=2)
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill="white")
            box = (tx - 12, ty - 12, tx + 12, ty + 12)
            if mode == "deaths":
                draw.rectangle(box, fill="#151b27", outline=color, width=2)
            else:
                draw.ellipse(box, fill="#151b27", outline=color, width=2)
            draw.text((tx, ty), str(n), anchor="mm", font=small, fill="white")
            legends.append(f"{n}={clock(event['t'])}")
        bottom = top + size + 8
        if not events:
            draw.text((x, bottom), "Aucune mort" if mode == "deaths" else "Aucun relevé disponible", font=small, fill="#becbdd")
        else:
            # Six relevés habituels en 5 minutes ; ne pas masquer silencieusement les suivants.
            for line in range(3):
                text = "  ".join(legends[line * 3:(line + 1) * 3])
                if text:
                    draw.text((x, bottom + line * 23), fit(text, size, small), font=small, fill="#dce5f2")
            if len(plotted) > 9 or len(plotted) < len(events):
                draw.text((x, bottom + 69), "Détails / positions absentes : voir légende", font=small, fill="#becbdd")
    note = "Carrés = morts · Position de l’événement" if mode == "deaths" else "Cercles = positions relevées · Aucun trajet interpolé entre deux relevés"
    draw.text((gap, canvas.height - 32), note, font=small, fill="#becbdd")
    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


def components(data, match_id, joueur, mode, page, mask):
    import interactions as discord
    page = min(max(page, 0), last_page(data))

    def token(action, *, view=mode, target=page, selected=mask):
        return f"lolmap_{action}_{match_id}_{joueur}_{view}_{target}_{selected}"

    def button(label, action, **kwargs):
        return discord.Button(label=label, style=discord.ButtonStyle.SECONDARY,
                              custom_id=token(action, **kwargs))

    options = [discord.StringSelectOption(
        label=f"{p['id']:02} · {p['champion']} · {p['name']}"[:100],
        description="Équipe bleue" if p["team"] == 100 else "Équipe rouge",
        value=str(p["id"]), default=bool(mask & (1 << (p["id"] - 1))),
    ) for p in data["players"]]
    previous = button("◀ 5 min", "prev", target=max(0, page - 1))
    previous.disabled = page == 0
    following = button("5 min ▶", "next", target=min(last_page(data), page + 1))
    following.disabled = page == last_page(data)
    return [
        discord.ActionRow(button("Morts" + (" ✓" if mode == "deaths" else ""), "mode", view="deaths"),
                          button("Déplacements" + (" ✓" if mode == "moves" else ""), "mode", view="moves")),
        discord.ActionRow(discord.StringSelectMenu(*options, custom_id=token("players"),
                          placeholder="Choisir de 1 à 10 joueurs", min_values=1, max_values=10)),
        discord.ActionRow(button("Les 10 joueurs", "all", selected=ALL_PLAYERS),
                          *[button(label, action, selected=sum(1 << (p["id"] - 1) for p in data["players"] if p["team"] == team))
                            for label, action, team in (("Équipe bleue", "blue", 100), ("Équipe rouge", "red", 200))]),
        discord.ActionRow(previous, following, button("Fermer", "close")),
    ]


def load_map(match_id, joueur):
    # Import différé : recap_details utilise aussi l'extracteur pur ci-dessus.
    from .recap_details import load_details
    loaded = load_details(match_id, joueur)
    if loaded is None:
        return None
    data = loaded[1].get("map")
    return data if data and data.get("version") == 1 else None


def map_response(match_id, joueur, mode, page, mask):
    import interactions as discord
    data = load_map(match_id, joueur)
    if data is None:
        return None
    page = min(max(0, page), last_page(data))
    mask &= ALL_PLAYERS
    if not mask:
        mask = ALL_PLAYERS
    start, end = window(data, page)
    embed = discord.Embed(title=f"Carte · {'Morts' if mode == 'deaths' else 'Déplacements'} · {clock(start)}–{clock(end)}",
                          description="Une carte par joueur. Choisis une équipe ou moins de joueurs pour agrandir.\n"
                                      "Les déplacements sont des positions relevées environ chaque minute, pas un trajet exact.",
                          color=0x69C8FF)
    identities = {p["id"]: p["champion"] for p in data["players"]}
    for player in selection(data, mask):
        events = player_events(data, player["id"], page, mode)
        details, n = [], 0
        for event in events:
            if event["xy"]:
                n += 1
            prefix = str(n) if event["xy"] else "Position absente"
            killer = identities.get(event.get("killer"), "environnement")
            details.append(f"{prefix} · {clock(event['t'])}" + (f" · {killer}" if mode == "deaths" else ""))
        label = f"{player['id']:02} · {player['champion']}"
        if details:
            value = "\n".join(details)
            if len(value) > 480:
                value = value[:450].rsplit("\n", 1)[0] + "\n… liste abrégée"
            embed.add_field(name=label, value=value, inline=True)
    embed.set_image(url="attachment://match_map.png")
    embed.set_footer(text=f"{match_id} · Fenêtre {page + 1}/{last_page(data) + 1} · Bleu / rouge : équipes Riot")
    return embed, render_map(data, mode, page, mask), components(data, match_id, joueur, mode, page, mask)
