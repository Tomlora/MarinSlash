"""Tests autonomes du récap de records : ni token Discord, ni base SQL, ni API Riot."""
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MATCH_DIR = ROOT / "fonctions" / "match"
COG_DIR = ROOT / "cogs"


class FakeField:
    def __init__(self, name, value, inline=False):
        self.name = name
        self.value = value
        self.inline = inline


class FakeEmbed:
    def __init__(self, title=None, description=None, color=None, **kwargs):
        self.title = title
        self.description = description
        self.color = color
        self.fields = []
        self.footer = None
        self.image = None

    def add_field(self, name, value, inline=False):
        self.fields.append(FakeField(name, value, inline))

    def set_footer(self, text):
        self.footer = text

    def set_image(self, url):
        self.image = types.SimpleNamespace(url=url)


class FakeButton:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class FakeActionRow:
    def __init__(self, *components):
        self.components = list(components)


class FakeSelect:
    def __init__(self, *options, **kwargs):
        self.options = options
        self.__dict__.update(kwargs)


def _load(source_name, path):
    spec = importlib.util.spec_from_file_location(source_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[source_name] = module
    spec.loader.exec_module(module)
    return module


def _load_under_stubs():
    original = {}
    targets = (
        "fonctions", "fonctions.match", "fonctions.match.records_display",
        "fonctions.match.records_ui", "fonctions.gestion_bdd", "interactions",
        "utils", "utils.emoji", "cogs", "cogs.lol_records",
    )
    for key in targets:
        original[key] = sys.modules.get(key)

    fake_discord = types.ModuleType("interactions")
    fake_discord.Embed = FakeEmbed
    fake_discord.Button = FakeButton
    fake_discord.ActionRow = FakeActionRow
    fake_discord.StringSelectMenu = FakeSelect
    fake_discord.StringSelectOption = lambda **kwargs: types.SimpleNamespace(**kwargs)
    fake_discord.ButtonStyle = types.SimpleNamespace(
        PRIMARY=1, SECONDARY=2, SUCCESS=3, DANGER=4
    )
    fake_discord.OptionType = types.SimpleNamespace(STRING=3)
    fake_discord.Extension = type("Extension", (), {})
    fake_discord.ComponentContext = type("ComponentContext", (), {})
    fake_discord.SlashContext = type("SlashContext", (), {})
    fake_discord.SlashCommandChoice = lambda **kwargs: types.SimpleNamespace(**kwargs)
    fake_discord.SlashCommandOption = lambda **kwargs: types.SimpleNamespace(**kwargs)
    fake_discord.component_callback = lambda *args, **kwargs: lambda fn: fn
    fake_discord.slash_command = lambda *args, **kwargs: lambda fn: fn

    functions = types.ModuleType("fonctions")
    functions.__path__ = [str(ROOT / "fonctions")]
    match_pkg = types.ModuleType("fonctions.match")
    match_pkg.__path__ = [str(MATCH_DIR)]
    fake_bdd = types.ModuleType("fonctions.gestion_bdd")
    fake_bdd.lire_bdd_perso = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("La démo ne doit pas accéder à PostgreSQL.")
    )
    fake_bdd.requete_perso_bdd = fake_bdd.lire_bdd_perso

    utils = types.ModuleType("utils")
    utils.__path__ = [str(ROOT / "utils")]
    fake_emoji = types.ModuleType("utils.emoji")
    fake_emoji.emote_champ_discord = {}
    fake_emoji.emote_v2 = {}
    fake_emoji.dict_place = {1: "🥇", 2: "🥈", 3: "🥉"}

    cogs = types.ModuleType("cogs")
    cogs.__path__ = [str(COG_DIR)]

    sys.modules.update({
        "fonctions": functions,
        "fonctions.match": match_pkg,
        "fonctions.gestion_bdd": fake_bdd,
        "interactions": fake_discord,
        "utils": utils,
        "utils.emoji": fake_emoji,
        "cogs": cogs,
    })
    try:
        display = _load(
            "fonctions.match.records_display", MATCH_DIR / "records_display.py"
        )
        ui = _load("fonctions.match.records_ui", MATCH_DIR / "records_ui.py")
        cog = _load("cogs.lol_records", COG_DIR / "lol_records.py")
        return display, ui, cog
    finally:
        for key, value in original.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


DISPLAY, UI, COG = _load_under_stubs()

COUNTS = {
    "none": 0,
    "alltime": 1,
    "personal": 1,
    "season": 1,
    "alltime_personal": 2,
    "all_scopes": 3,
    "tie": 2,
    "podium": 3,
    "ten": 10,
    "twenty_five": 25,
    "fifty": 50,
    "mixed": 21,
}


def test_all_demo_scenarios_have_expected_counts():
    assert set(COG.DEMO_SCENARIOS) == set(COUNTS)
    for scenario, expected in COUNTS.items():
        collector = COG.demo_collector(scenario)
        assert collector.count() == expected, scenario


def test_none_is_a_legitimate_one_page_result():
    empty = COG.demo_collector("none")
    embed = FakeEmbed()
    UI.add_featured_records(embed, empty)
    assert "Aucun record" in embed.fields[0].value
    pages = UI.build_record_pages(empty, "DEMO", demo=True)
    assert len(pages) == 1
    assert pages[0][0] == "aperçu"
    controls = COG._page_components("d", "none", 0, pages, 0)
    assert controls[0].components[0].disabled is True
    assert controls[0].components[1].disabled is True


def test_simultaneous_scopes_are_one_highlight_but_multiple_details():
    c = COG.demo_collector("alltime_personal")
    assert len(UI.grouped_records(c)) == 1
    assert len(UI.featured_records(c)) == 1
    embed = FakeEmbed()
    UI.add_featured_records(embed, c)
    assert "Historique" in embed.fields[0].value
    assert "Personnel" in embed.fields[0].value
    assert len(UI.build_record_pages(c, "DEMO")) == 3


def test_all_scopes_preserved_in_detail():
    c = COG.demo_collector("all_scopes")
    pages = UI.build_record_pages(c, "DEMO", demo=True)
    assert [scope for scope, _ in pages] == [
        "aperçu", "alltime", "general", "perso"
    ]


def test_ties_and_podiums_are_labeled_differently():
    tie = UI.build_record_pages(COG.demo_collector("tie"), "DEMO")
    podium = UI.build_record_pages(COG.demo_collector("podium"), "DEMO")
    assert any(
        "Égalisation" in field.name
        for _, page in tie[1:]
        for field in page.fields
    )
    assert any(
        "Entrée Top" in field.name
        for _, page in podium[1:]
        for field in page.fields
    )


def test_long_pages_fit_all_discord_embed_limits_and_never_drop_entries():
    for scenario in ("ten", "twenty_five", "fifty", "mixed"):
        collector = COG.demo_collector(scenario)
        pages = UI.build_record_pages(collector, "EUW1_1234567890", demo=True)
        assert len(pages) > 1
        assert sum(len(embed.fields) for _, embed in pages[1:]) == collector.count()
        assert len({field.name for _, page in pages[1:] for field in page.fields}) > 5
        for _, embed in pages:
            assert len(embed.title) <= 256
            assert len(embed.description) <= 4096
            assert len(embed.fields) <= 5
            assert len(embed.footer) <= 2048
            assert all(len(field.name) <= 256 for field in embed.fields)
            assert all(len(field.value) <= 1024 for field in embed.fields)
            text_length = len(embed.title) + len(embed.description) + len(embed.footer)
            text_length += sum(len(f.name) + len(f.value) for f in embed.fields)
            assert text_length <= 6000, scenario


def test_pagination_navigation_reaches_last_page():
    collector = COG.demo_collector("fifty")
    pages = UI.build_record_pages(collector, "DEMO")
    assert len(pages) == 13
    first = COG._page_components("d", "fifty", 0, pages, 0)
    last = COG._page_components("d", "fifty", 0, pages, len(pages) - 1)
    assert first[0].components[0].disabled
    assert not first[0].components[1].disabled
    assert not last[0].components[0].disabled
    assert last[0].components[1].disabled
    assert len(first) <= 5
    assert all(len(row.components) <= 5 for row in first)


def test_button_and_match_ids_remain_under_custom_id_limit():
    button = UI.make_open_button("EUW1_1234567890", 123456789)
    assert COG.OPEN_RE.fullmatch(button.custom_id)
    assert len(button.custom_id) <= 100
    assert COG._normalize_match_id("1234567890") == "EUW1_1234567890"
    assert COG._normalize_match_id("euw1-1234567890") == "EUW1_1234567890"
    controls = COG._page_components(
        "r", "EUW1_1234567890", 123456789,
        UI.build_record_pages(COG.demo_collector("ten"), "DEMO"), 0,
    )
    assert all(
        len(component.custom_id) <= 100
        for row in controls for component in row.components
    )


def test_demo_selector_includes_every_case():
    controls = COG._demo_components("none")
    assert len(controls) == 2
    options = controls[0].components[0].options
    assert {option.value for option in options} == set(COUNTS)
    assert len(options) <= 25


def test_snapshot_roundtrip_keeps_both_distinctions_and_no_records():
    old_write = UI.requete_perso_bdd
    old_read = UI.lire_bdd_perso
    old_schema = UI.SCHEMA_READY
    try:
        UI.SCHEMA_READY = True
        captured = {}

        def write(sql, params):
            captured["payload"] = params["data"]
            captured["sql"] = sql

        UI.requete_perso_bdd = write
        UI.lire_bdd_perso = lambda *args, **kwargs: pd.DataFrame(
            [{"data": json.loads(captured["payload"])}]
        ).T

        original = COG.demo_collector("alltime_personal")
        assert UI.save_record_snapshot("EUW1_1234567890", 3, original)
        assert "ON CONFLICT" in captured["sql"]
        restored = UI.load_record_snapshot("EUW1_1234567890", 3)
        assert restored.count() == 2
        assert {entry.scope for scope in restored.records
                for entry in restored.records[scope]} == {"alltime", "perso"}

        assert UI.save_record_snapshot("EUW1_1234567890", 3, COG.demo_collector("none"))
        assert UI.load_record_snapshot("EUW1_1234567890", 3).is_empty()
    finally:
        UI.requete_perso_bdd = old_write
        UI.lire_bdd_perso = old_read
        UI.SCHEMA_READY = old_schema


def test_demo_scoreboard_is_generated_offline():
    from PIL import Image

    path = COG._demo_image()
    try:
        with Image.open(path) as image:
            assert image.size == (1140, 430)
            assert image.format == "PNG"
    finally:
        os.unlink(path)
