"""Smoke tests avec interactions.py 5.13.2 (vraies classes Discord, aucun réseau)."""
import importlib.util
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
        "fonctions.match.records_ui", "fonctions.gestion_bdd", "utils",
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
        return ui, cog
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


UI, COG = _load_bot_modules()


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
