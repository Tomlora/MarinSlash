"""Smoke tests avec interactions.py 5.13.2 (vraies classes Discord, aucun réseau)."""
import importlib.util
import inspect
import sys
import types
from pathlib import Path

import interactions


ROOT = Path(__file__).resolve().parents[1]
MATCH_DIR = ROOT / "fonctions" / "match"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_bot_modules():
    names = (
        "fonctions", "fonctions.match", "fonctions.match.records_display",
        "fonctions.match.records_ui", "fonctions.match.records_preferences",
        "fonctions.match.match_views", "fonctions.match.recap_details", "cogs.settings_records", "cogs.lol_match_views",
        "fonctions.gestion_bdd", "utils",
        "utils.emoji", "cogs", "cogs.lol_records",
    )
    previous = {key: sys.modules.get(key) for key in names}
    functions = types.ModuleType("fonctions")
    functions.__path__ = [str(ROOT / "fonctions")]
    match = types.ModuleType("fonctions.match")
    match.__path__ = [str(MATCH_DIR)]
    database = types.ModuleType("fonctions.gestion_bdd")
    database.lire_bdd_perso = lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("Pas de connexion PostgreSQL dans le smoke test.")
    )
    database.requete_perso_bdd = database.lire_bdd_perso
    utils = types.ModuleType("utils")
    utils.__path__ = [str(ROOT / "utils")]
    emoji = types.ModuleType("utils.emoji")
    emoji.emote_v2 = {}
    emoji.emote_champ_discord = {}
    emoji.dict_place = {1: "🥇", 2: "🥈", 3: "🥉"}
    cogs = types.ModuleType("cogs")
    cogs.__path__ = [str(ROOT / "cogs")]
    sys.modules.update({
        "fonctions": functions, "fonctions.match": match,
        "fonctions.gestion_bdd": database,
        "utils": utils, "utils.emoji": emoji, "cogs": cogs,
    })
    try:
        _load("fonctions.match.records_display", MATCH_DIR / "records_display.py")
        ui = _load("fonctions.match.records_ui", MATCH_DIR / "records_ui.py")
        cog = _load("cogs.lol_records", ROOT / "cogs" / "lol_records.py")
        preferences = sys.modules["fonctions.match.records_preferences"]
        views = _load("fonctions.match.match_views", MATCH_DIR / "match_views.py")
        details = _load("fonctions.match.recap_details", MATCH_DIR / "recap_details.py")
        view_cog = _load("cogs.lol_match_views", ROOT / "cogs" / "lol_match_views.py")
        settings = _load("cogs.settings_records", ROOT / "cogs" / "settings_records.py")
        return ui, cog, preferences, views, view_cog, settings, details
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


UI, COG, PREFS, VIEWS, VIEW_COG, SETTINGS, DETAILS = _load_bot_modules()


def test_real_embed_and_button_components():
    collector = COG.demo_collector("all_scopes")
    embed = interactions.Embed(title="Récap", color=0x5865F2)
    UI.add_featured_records(embed, collector)
    assert len(embed.fields) == 1
    assert "Historique" in embed.fields[0].value

    button = UI.make_open_button("EUW1_1234567890", 1234)
    discord_row = interactions.ActionRow(button).to_dict()
    assert discord_row["components"][0]["custom_id"] == button.custom_id

    pages = UI.build_record_pages(collector, "EUW1_1234567890")
    assert len(pages) == 4
    assert all(isinstance(entry, interactions.Embed) for _, entry in pages)
    for index in range(len(pages)):
        rows = COG._page_components("r", "EUW1_1234567890", 1234, pages, index)
        assert len(rows) <= 5
        assert all(len(row.to_dict()["components"]) <= 5 for row in rows)


def test_real_demo_selector_renders_native_discord_components():
    components = COG._demo_components("fifty")
    assert len(components) == 2
    menu = components[0].to_dict()["components"][0]
    button = components[1].to_dict()["components"][0]
    assert menu["custom_id"] == "lolrec_demo_select"
    assert len(menu["options"]) == 12
    assert button["custom_id"] == "lolrec_demo_open_fifty"

    embed = COG._demo_embed("ten", "attachment://scoreboard.png")
    assert isinstance(embed, interactions.Embed)
    assert embed.image.url == "attachment://scoreboard.png"


def test_actual_file_wrapper_accepts_generated_demo_image():
    import os

    path = COG._demo_image()
    try:
        upload = interactions.File(path)
        assert upload is not None
    finally:
        os.unlink(path)


def test_actual_class_accepts_all_offline_scenarios():
    for scenario in COG.DEMO_SCENARIOS:
        collector = COG.demo_collector(scenario)
        pages = UI.build_record_pages(collector, "EUW1_1234567890", demo=True)
        assert pages
        assert all(len(embed.fields) <= 5 for _, embed in pages)


def test_interactions_5132_supports_deferred_editing_and_ephemeral_response():
    # Ces signatures viennent de la version réellement installée en CI.
    defer = inspect.signature(interactions.ComponentContext.defer)
    assert "ephemeral" in defer.parameters
    assert "edit_origin" in defer.parameters
    assert hasattr(interactions.ComponentContext, "edit_origin")
    assert "ephemeral" in inspect.signature(interactions.ComponentContext.send).parameters


def test_serialized_component_ids_are_unique_across_all_rows():
    # Les classes Discord sérialisent les composants mais ne détectent pas
    # les collisions entre rangées : vérifier le payload envoyé à l'API.
    for scenario in COG.DEMO_SCENARIOS:
        pages = UI.build_record_pages(COG.demo_collector(scenario), "EUW1_1234567890")
        for kind, key in (("d", scenario), ("r", "EUW1_1234567890")):
            for index in range(len(pages)):
                rows = COG._page_components(kind, key, 123456789, pages, index)
                components = [
                    component
                    for row in rows
                    for component in row.to_dict()["components"]
                ]
                ids = [component["custom_id"] for component in components]
                assert len(ids) == len(set(ids)), (scenario, kind, index, ids)
                assert all(len(custom_id) <= 100 for custom_id in ids)
                for custom_id in ids:
                    if custom_id != "lolrec_close":
                        assert COG.PAGE_RE.fullmatch(custom_id)


def test_new_views_serialize_native_components_and_bounded_embeds():
    buttons = VIEWS.make_match_buttons("EUW1_1234567890", 123456789, UI.make_open_button("EUW1_1234567890", 123456789))
    assert len(buttons[0].to_dict()["components"]) == 5
    match = {"match_id": "EUW1_1234567890", "player_name": "Marin#TEST", "mode": "ARAM"}
    pages = VIEWS.build_teamfight_pages(match, [], False) + VIEWS.build_gank_pages(match, {}, [])
    for page in pages:
        payload = page.to_dict()
        assert len(payload["fields"]) <= 5
        assert all(len(field["value"]) <= 1024 for field in payload["fields"])
    for kind in ("teamfight", "ganks", "score", "analysis", "progress"):
        for index in range(len(pages)):
            rows = VIEW_COG.page_components(kind, "EUW1_1234567890", 123456789, index, len(pages))
            ids = [b["custom_id"] for row in rows for b in row.to_dict()["components"]]
            assert len(ids) == len(set(ids))
    for layout in ("compact", "sections"):
        prefs = PREFS.RecordPreferences(layout, ("perso",))
        embed = interactions.Embed(title="Récap")
        UI.add_featured_records(embed, COG.demo_collector("all_scopes"), preferences=prefs)
        assert len(embed.to_dict()["fields"][0]["value"]) <= 960
        assert isinstance(SETTINGS.settings_embed(prefs), interactions.Embed)


def test_real_score_pages_and_gold_image_upload_render_offline():
    from io import BytesIO
    from PIL import Image
    from test_match_records_ui import sample_details_match

    data = DETAILS.snapshot(sample_details_match())
    match = {"match_id": "EUW1_123", "player_name": "Player7#TEST", "mode": "RANKED", "id_participant": 7}
    pages = DETAILS.build_score_pages(match, data["scores"])
    assert len(pages) == 4
    for page in pages:
        payload = page.to_dict()
        assert len(payload["fields"]) <= 5
        assert all(len(f["value"]) <= 1024 for f in payload["fields"])
    from unittest.mock import patch
    from matplotlib.figure import Figure
    import math
    original_save = Figure.savefig
    curves = []
    def capture(figure, *args, **kwargs):
        curves.extend([line.get_ydata().tolist() for line in figure.axes[0].lines[:2]])
        return original_save(figure, *args, **kwargs)
    with patch.object(Figure, "savefig", capture):
        png = DETAILS.render_gold(data["gold"])
    assert curves[0][:3] == [0, 500, 1000]
    assert curves[1][:3] == [0, -500, -1000]
    assert math.isnan(curves[0][3]) and math.isnan(curves[1][3])
    assert curves[0][4] == 2000 and curves[1][4] == -2000
    with Image.open(BytesIO(png)) as image:
        assert image.size == (1440, 660) and image.format == "PNG"
        assert len(image.convert("RGB").getcolors(maxcolors=1000000)) > 100
    file = interactions.File(BytesIO(png), file_name="gold_diff.png")
    assert file.file_name == "gold_diff.png"
    embed = DETAILS.gold_embed(match, data["gold"])
    assert embed.to_dict()["image"]["url"] == "attachment://gold_diff.png"
    assert "file" in inspect.signature(interactions.ComponentContext.send).parameters
    assert "attachments" in inspect.signature(interactions.ComponentContext.edit_origin).parameters
    # Courbe à zéro et une seule minute : limites valides et PNG lisible.
    for points in ([{"minute": 0, "blue": 2500, "red": 2500}],
                   [{"minute": m, "blue": 2500, "red": 3500} for m in range(120)]):
        with Image.open(BytesIO(DETAILS.render_gold(points))) as image:
            assert image.size == (1440, 660)
