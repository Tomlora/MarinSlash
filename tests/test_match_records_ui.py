"""Tests autonomes du récap de records : ni token Discord, ni base SQL, ni API Riot."""
import asyncio
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
        "fonctions.match.records_ui", "fonctions.match.records_preferences",
        "fonctions.match.match_views", "cogs.settings_records", "cogs.lol_match_views",
        "fonctions.gestion_bdd", "interactions",
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
    fake_discord.OptionType = types.SimpleNamespace(STRING=3, BOOLEAN=5)
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
    fake_emoji.emote_champ_discord = {
        "Viego": "<:Viego:123456789012345678>",
        "Ahri": "<:Ahri:234567890123456789>",
        "Kaisa": "<:Kaisa:345678901234567890>",
        "LeeSin": "<:LeeSin:456789012345678901>",
    }
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
        preferences = sys.modules["fonctions.match.records_preferences"]
        views = _load("fonctions.match.match_views", MATCH_DIR / "match_views.py")
        view_cog = _load("cogs.lol_match_views", COG_DIR / "lol_match_views.py")
        settings = _load("cogs.settings_records", COG_DIR / "settings_records.py")
        return display, ui, cog, preferences, views, view_cog, settings
    finally:
        for key, value in original.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


DISPLAY, UI, COG, PREFS, VIEWS, VIEW_COG, SETTINGS = _load_under_stubs()

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


def test_simultaneous_scopes_are_one_selected_statistic_with_separate_sections():
    c = COG.demo_collector("alltime_personal")
    assert len(UI.grouped_records(c)) == 1
    assert len(UI.featured_records(c)) == 1
    embed = FakeEmbed()
    UI.add_featured_records(embed, c)
    assert "Historique" in embed.fields[0].value
    assert "Personnel" in embed.fields[0].value
    assert len(UI.build_record_pages(c, "DEMO")) == 3


def test_previous_holder_and_champion_are_kept_in_featured_recaps():
    collector = DISPLAY.RecordsCollector()
    collector.add(DISPLAY.RecordEntry(
        scope="alltime", place=1, category="dmg", value=14000,
        old_record=12490, old_holder="JoueurHistorique",
        old_champion="Viego",
    ))
    collector.add(DISPLAY.RecordEntry(
        scope="general", place=1, category="dmg", value=14000,
        old_record=11980, old_holder="JoueurSaison",
        old_champion="Ahri",
    ))
    embed = FakeEmbed()
    UI.add_featured_records(embed, collector)
    value = embed.fields[0].value
    assert "Historique" in value
    assert "Saison" in value
    assert "12 490" in value or "12490" in value
    assert "JoueurHistorique <:Viego:123456789012345678>" in value
    assert "JoueurSaison <:Ahri:234567890123456789>" in value
    assert "(Viego)" not in value and "(Ahri)" not in value
    assert len(value) <= 1024


def test_same_previous_record_is_not_repeated_across_scopes():
    collector = DISPLAY.RecordsCollector()
    for scope in ("alltime", "general", "perso"):
        collector.add(DISPLAY.RecordEntry(
            scope=scope, place=1, category="dmg", value=14000,
            old_record=12490, old_holder="MemeJoueur",
            old_champion="Viego",
        ))
    value = UI._featured_line("dmg", UI.grouped_records(collector)["dmg"])
    assert value.count("MemeJoueur") == 1
    assert "Historique" in value and "Saison" in value and "Personnel" in value


class RecordingContext:
    def __init__(self, custom_id):
        self.custom_id = custom_id
        self.calls = []

    async def defer(self, **kwargs):
        self.calls.append(("defer", kwargs))

    def validate_components(self, kwargs):
        ids = [
            component.custom_id
            for row in kwargs.get("components", [])
            for component in row.components
        ]
        assert len(ids) == len(set(ids)), "component_custom_id_duplicated"

    async def send(self, content=None, **kwargs):
        self.validate_components(kwargs)
        self.calls.append(("send", content, kwargs))

    async def edit_origin(self, **kwargs):
        self.validate_components(kwargs)
        self.calls.append(("edit_origin", kwargs))


def test_real_open_always_finishes_its_deferred_response():
    old_load = COG.load_record_snapshot
    old_build = COG.build_record_pages
    try:
        COG.load_record_snapshot = lambda *_: COG.demo_collector("all_scopes")
        cog = COG.LolRecords.__new__(COG.LolRecords)
        ctx = RecordingContext("lolrec_open_EUW1_7996537266_5")
        asyncio.run(cog.on_real_open(ctx))
        assert ctx.calls[0] == ("defer", {"ephemeral": True})
        assert ctx.calls[-1][0] == "send"
        assert ctx.calls[-1][2]["ephemeral"] is True
        assert "embeds" in ctx.calls[-1][2]

        def raises(*args, **kwargs):
            raise RuntimeError("Erreur de construction du paginator")

        COG.build_record_pages = raises
        failed_ctx = RecordingContext("lolrec_open_EUW1_7996537266_5")
        asyncio.run(cog.on_real_open(failed_ctx))
        assert failed_ctx.calls[0][0] == "defer"
        assert failed_ctx.calls[-1][0] == "send"
        assert "Impossible" in failed_ctx.calls[-1][1]
    finally:
        COG.load_record_snapshot = old_load
        COG.build_record_pages = old_build


def test_slow_database_returns_terminal_message_not_infinite_spinner():
    import time

    old_load = COG.load_record_snapshot
    old_timeout = COG.RECORD_LOAD_TIMEOUT_SECONDS
    try:
        COG.load_record_snapshot = lambda *_: time.sleep(0.04)
        COG.RECORD_LOAD_TIMEOUT_SECONDS = 0.001
        ctx = RecordingContext("lolrec_open_EUW1_7996537266_5")
        cog = COG.LolRecords.__new__(COG.LolRecords)
        asyncio.run(cog.on_real_open(ctx))
        assert ctx.calls[0][0] == "defer"
        assert ctx.calls[-1][0] == "send"
        assert "trop de temps" in ctx.calls[-1][1]
    finally:
        COG.load_record_snapshot = old_load
        COG.RECORD_LOAD_TIMEOUT_SECONDS = old_timeout


def test_navigation_defers_edit_and_acknowledges_database_errors():
    old_load = COG.load_record_snapshot
    try:
        COG.load_record_snapshot = lambda *_: COG.demo_collector("ten")
        cog = COG.LolRecords.__new__(COG.LolRecords)
        ctx = RecordingContext("lolrec_page_r_EUW1_7996537266_5_1")
        asyncio.run(cog.on_page(ctx))
        assert ctx.calls[0] == ("defer", {"edit_origin": True})
        assert ctx.calls[-1][0] == "edit_origin"
        assert "embeds" in ctx.calls[-1][1]

        def raises(*args, **kwargs):
            raise RuntimeError("DB indisponible")

        COG.load_record_snapshot = raises
        failed_ctx = RecordingContext("lolrec_page_r_EUW1_7996537266_5_1")
        asyncio.run(cog.on_page(failed_ctx))
        assert failed_ctx.calls[0][0] == "defer"
        assert failed_ctx.calls[-1][0] == "edit_origin"
        assert "Impossible" in failed_ctx.calls[-1][1]["content"]
    finally:
        COG.load_record_snapshot = old_load


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
        "Égalisation" in field.value
        for _, page in tie[1:]
        for field in page.fields
    )
    assert any(
        "Top " in field.value
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


def test_every_paginator_message_has_unique_ids_and_valid_targets():
    for scenario in COG.DEMO_SCENARIOS:
        pages = UI.build_record_pages(COG.demo_collector(scenario), "EUW1_1234567890")
        for kind, key in (("d", scenario), ("r", "EUW1_1234567890")):
            for index in range(len(pages)):
                rows = COG._page_components(kind, key, 123456789, pages, index)
                buttons = [button for row in rows for button in row.components]
                ids = [button.custom_id for button in buttons]
                assert len(ids) == len(set(ids)), (scenario, kind, index, ids)
                for button in buttons:
                    assert len(button.custom_id) <= 100
                    if button.custom_id == "lolrec_close":
                        continue
                    match = COG.PAGE_RE.fullmatch(button.custom_id)
                    assert match is not None, button.custom_id
                    parsed_kind, parsed_key, player, target = match.groups()
                    assert (parsed_kind, parsed_key, player) == (kind, key, "123456789")
                    assert 0 <= int(target) < len(pages)


def test_compact_record_line_keeps_score_holder_and_champion_together():
    entry = DISPLAY.RecordEntry(
        scope="general", place=5, category="tf_damage_window", value=13401,
        old_record=13290, old_holder="<@123456789012345678>", old_champion="Ahri",
    )
    line = UI._featured_line(entry.category, [entry])
    first_line = line.splitlines()[0]
    assert "**dmg max en teamfight** → `13401`" in first_line
    assert "~~13290~~ <@123456789012345678> <:Ahri:234567890123456789>" in first_line
    assert "(Ahri)" not in line
    _, detail = UI._detail_field(entry)
    assert "→ `13401` ・ ~~13290~~" in detail
    assert "<:Ahri:234567890123456789>" in detail
    assert "Top 5" in detail
    entry.is_tie = True
    entry.old_record = entry.value
    assert "Égalise" in UI._featured_line(entry.category, [entry])
    assert "~~" not in UI._detail_field(entry)[1]


def test_champion_icons_tolerate_riot_spelling_and_missing_icons():
    for name, key in (("aHrI", "Ahri"), ("Kai'Sa", "Kaisa"), ("Lee Sin", "LeeSin")):
        assert UI._champion_icon(name) == UI.emote_champ_discord[key]
    assert UI._champion_icon(None) == ""
    assert UI._champion_icon("Unknown champion") == ""


def test_new_controls_and_legacy_buttons_reach_the_expected_page():
    cog = COG.LolRecords.__new__(COG.LolRecords)
    for scenario in COG.DEMO_SCENARIOS:
        pages = UI.build_record_pages(COG.demo_collector(scenario), "EUW1_1234567890")
        ctx = RecordingContext(f"lolrec_demo_open_{scenario}")
        asyncio.run(cog.on_demo_open(ctx))
        assert ctx.calls[0] == ("defer", {"ephemeral": True})
        assert "embeds" in ctx.calls[-1][2]
        for index in range(len(pages)):
            for row in COG._page_components("d", scenario, 0, pages, index):
                for button in row.components:
                    if getattr(button, "disabled", False):
                        continue
                    if button.custom_id == "lolrec_close":
                        continue
                    match = COG.PAGE_RE.fullmatch(button.custom_id)
                    target = int(match.group(4))
                    ctx = RecordingContext(button.custom_id)
                    asyncio.run(cog.on_page(ctx))
                    assert ctx.calls[0] == ("defer", {"edit_origin": True})
                    assert ctx.calls[-1][0] == "edit_origin"
                    assert ctx.calls[-1][1]["embeds"].footer.startswith(
                        f"Page {target + 1}/{len(pages)}"
                    )
    ctx = RecordingContext("lolrec_page_d_all_scopes_0_2")
    asyncio.run(cog.on_page(ctx))
    assert ctx.calls[-1][1]["embeds"].footer.startswith("Page 3/4")


def test_public_recap_uses_old_scope_sections_and_complete_record_lines():
    collector = DISPLAY.RecordsCollector()
    for scope, place, category, score, old, champion in (
        ("alltime", 5, "tf_physical_damage_window", 12536, 12490, "Ahri"),
        ("alltime", 8, "tf_damage_window", 13401, 13364, "Viego"),
        ("general", 5, "tf_physical_damage_window", 12536, 12490, "Ahri"),
        ("general", 5, "tf_damage_window", 13401, 13290, "Ahri"),
    ):
        collector.add(DISPLAY.RecordEntry(
            scope, place, category, score, old, "<@123456789012345678>", champion
        ))
    embed = FakeEmbed()
    UI.add_featured_records(embed, collector, preferences=PREFS.RecordPreferences(layout='sections'))
    field = embed.fields[0]
    assert field.name == "Exploits"
    alltime, season, footer = field.value.split("\n\n")
    assert alltime.splitlines()[0] == DISPLAY.SCOPE_CONFIG["alltime"]["header"]
    assert season.splitlines()[0] == DISPLAY.SCOPE_CONFIG["general"]["header"]
    assert len(alltime.splitlines()) == len(season.splitlines()) == 3
    assert "→ `12536` ・ ~~12490~~" in alltime
    assert "→ `12536` ・ ~~12490~~" in season
    assert "#8 **dmg max en teamfight** → `13401` ・ ~~13364~~" in alltime
    assert "#5 **dmg max en teamfight** → `13401` ・ ~~13290~~" in season
    for line in alltime.splitlines()[1:] + season.splitlines()[1:]:
        assert "<@123456789012345678> <:" in line
    assert footer == "4 distinctions · 2 statistiques"
    assert "↳" not in field.value
    assert "Records Perso" not in field.value


def test_public_recap_limits_statistics_without_cutting_their_scopes():
    import re

    collectors = [COG.demo_collector(scenario) for scenario in COG.DEMO_SCENARIOS]
    long = DISPLAY.RecordsCollector()
    for category in (
        "tf_dead_damage_share_pct", "tf_damage_window_share_pct", "vision_score", "gold_min"
    ):
        for scope in UI.SCOPES:
            long.add(DISPLAY.RecordEntry(
                scope, 1, category, 99, 88, "Détenteur" * 30, "Viego",
            ))
    collectors.append(long)
    for collector in collectors:
        embed = FakeEmbed()
        UI.add_featured_records(embed, collector, preferences=PREFS.RecordPreferences(layout='sections'))
        text = embed.fields[0].value
        assert len(text) <= 960
        shown = set(re.findall(r"\*\*([^*]+)\*\* →", text))
        assert len(shown) <= 3
        if collector.is_empty():
            continue
        assert shown
        for scope in UI.SCOPES:
            expected = [
                entry for entry in collector.records.get(scope, [])
                if UI.display_label(entry.category) in shown
            ]
            sections = [
                section for section in text.split("\n\n")
                if section.startswith(DISPLAY.SCOPE_CONFIG[scope]["header"])
            ]
            if not expected:
                assert not sections
                continue
            assert len(sections) == 1
            assert len(sections[0].splitlines()) - 1 == len(expected)
            for entry in expected:
                assert f"**{UI.display_label(entry.category)}** →" in sections[0]
        hidden = len(UI.grouped_records(collector)) - len(shown)
        if hidden:
            assert f"**+{hidden} autre(s) statistique(s)**" in text
        # Le détail reste exhaustif, même si le récap atteint son budget.
        pages = UI.build_record_pages(collector, "EUW1_1234567890")
        assert sum(len(page.fields) for _, page in pages[1:]) == collector.count()


def test_preferences_default_and_all_scope_combinations_in_both_layouts():
    from itertools import product

    assert PREFS.RecordPreferences().layout == "compact"
    original = COG.demo_collector("all_scopes")
    for layout in PREFS.LAYOUTS:
        for enabled in product((False, True), repeat=3):
            scopes = tuple(s for s, show in zip(UI.SCOPES, enabled) if show)
            prefs = PREFS.RecordPreferences(layout, scopes)
            filtered = PREFS.filter_records(original, prefs)
            assert filtered.count() == len(scopes)
            assert original.count() == 3
            embed = FakeEmbed()
            UI.add_featured_records(embed, original, preferences=prefs)
            pages = UI.build_record_pages(original, "EUW1_1", preferences=prefs)
            assert [scope for scope, _ in pages[1:]] == list(scopes)
            if not scopes:
                assert not embed.fields
                assert "/settings_records" in pages[0][1].fields[0].value
            else:
                assert len(embed.fields[0].value) <= 960
                if layout == "compact":
                    assert "↳" in embed.fields[0].value
                else:
                    assert "↳" not in embed.fields[0].value


def test_settings_update_only_the_calling_discord_user_and_preserve_false():
    old_save, old_load = SETTINGS.save_preferences, SETTINGS.load_preferences
    calls = []
    try:
        SETTINGS.save_preferences = lambda *args: calls.append(args)
        SETTINGS.load_preferences = lambda *args, **kwargs: PREFS.RecordPreferences("sections", ())
        cog = SETTINGS.SettingsRecords.__new__(SETTINGS.SettingsRecords)
        ctx = RecordingContext("")
        ctx.author = types.SimpleNamespace(id=123)
        asyncio.run(cog.settings_records(ctx, format="sections", alltime=False, saison=False, perso=False))
        assert calls == [(123, "sections", False, False, False)]
        assert ctx.calls[0] == ("defer", {"ephemeral": True})
        assert ctx.calls[-1][2]["ephemeral"]
        assert "Aucune" in ctx.calls[-1][2]["embeds"].fields[1].value
        calls.clear()
        asyncio.run(cog.settings_records(ctx))
        assert not calls
    finally:
        SETTINGS.save_preferences, SETTINGS.load_preferences = old_save, old_load


def test_settings_database_failure_is_reported_without_success_message():
    old = SETTINGS.save_preferences
    try:
        def fails(*args):
            raise RuntimeError("DB unavailable")
        SETTINGS.save_preferences = fails
        ctx = RecordingContext("")
        ctx.author = types.SimpleNamespace(id=123)
        cog = SETTINGS.SettingsRecords.__new__(SETTINGS.SettingsRecords)
        asyncio.run(cog.settings_records(ctx, perso=False))
        assert "Impossible" in ctx.calls[-1][1]
        assert "embeds" not in ctx.calls[-1][2]
    finally:
        SETTINGS.save_preferences = old


def test_preference_storage_uses_bound_parameters_and_rejects_invalid_layout():
    old = PREFS.requete_perso_bdd
    calls = []
    try:
        PREFS.requete_perso_bdd = lambda *args: calls.append(args)
        PREFS.save_preferences(123, perso=False)
        assert calls[-1][1] == {"discord": 123, "layout": None, "alltime": None, "saison": None, "perso": False}
        assert "ON CONFLICT" in calls[-1][0]
        calls.clear()
        try:
            PREFS.save_preferences(123, layout="invalid")
            assert False
        except ValueError:
            pass
        assert not calls
    finally:
        PREFS.requete_perso_bdd = old


def test_private_record_buttons_use_viewer_preferences_on_every_page():
    old_load, old_prefs = COG.load_record_snapshot, COG.load_preferences
    collector = COG.demo_collector("all_scopes")
    users = []
    try:
        COG.load_record_snapshot = lambda *args: collector
        def prefs(discord):
            users.append(discord)
            return PREFS.RecordPreferences("compact", ("perso",))
        COG.load_preferences = prefs
        cog = COG.LolRecords.__new__(COG.LolRecords)
        ctx = RecordingContext("lolrec_open_EUW1_123_5")
        ctx.author = types.SimpleNamespace(id=456)
        asyncio.run(cog.on_real_open(ctx))
        rows = ctx.calls[-1][2]["components"]
        assert [b.label for b in rows[1].components] == ["Aperçu", "Personnel"]
        page = RecordingContext("lolrec_page_r_EUW1_123_5_1_next")
        page.author = ctx.author
        asyncio.run(cog.on_page(page))
        assert "Personnel" in page.calls[-1][1]["embeds"].title
        assert users == [456, 456]
        assert collector.count() == 3
    finally:
        COG.load_record_snapshot, COG.load_preferences = old_load, old_prefs


def example_match():
    return {"match_id": "EUW1_123", "joueur": 5, "player_name": "Marin#TEST",
            "mode": "RANKED", "date": 2000, "champion": "Ahri", "role": "MID",
            "victoire": True, "time": 32.05, "kills": 12, "deaths": 3, "assists": 9,
            "dmg_min": 900, "cs_min": 8, "gold_min": 450, "vision_score": 30,
            "kp": 70, "kda": 7, "vision_min": 0.9}


def test_analysis_and_progression_pages_are_bounded_and_keep_all_fights():
    match = example_match()
    fights = [{"start_ms": i * 60000, "end_ms": i * 60000 + 45000,
               "damage_window_estimated": 1000 + i, "fight_kills": 2,
               "fight_deaths": 0, "fight_assists": 3, "allied_kills": 4, "enemy_kills": 1}
              for i in range(17)]
    analysis = VIEWS.build_analysis_pages(match, fights)
    chronology = [p for p in analysis if "Chronologie" in p.title]
    assert sum(len(p.fields) for p in chronology) == 17
    assert "32:05" in analysis[0].fields[0].value
    history = [{**match, "match_id": f"EUW1_{i}", "date": i, "dmg_min": 800} for i in range(10)]
    progression = VIEWS.build_progress_pages(match, history)
    for page in analysis + progression:
        assert len(page.fields) <= 5
        assert all(len(f.value) <= 1024 for f in page.fields)
        assert sum(len(f.name) + len(f.value) for f in page.fields) + len(page.description) + len(page.title) + len(page.footer) <= 6000
    history_pages = [p for p in progression if "référence" in p.title]
    assert sum(len(p.fields) for p in history_pages) == 10
    assert "+100" in VIEWS.comparison(match, history, "dmg_min")
    assert "+12.5" in VIEWS.comparison(match, history, "dmg_min")


def test_progression_handles_null_zero_and_short_history_without_invented_values():
    match = example_match()
    assert "Aucune valeur antérieure" in VIEWS.comparison(match, [], "dmg_min")
    assert "non enregistrée" in VIEWS.comparison({}, [{"dmg_min": 10}], "dmg_min")
    assert "nan" not in VIEWS.comparison(match, [{"dmg_min": float("nan")}], "dmg_min")
    zero = VIEWS.comparison(match, [{"dmg_min": 0}], "dmg_min")
    assert "+900" in zero and "%" not in zero
    pages = VIEWS.build_progress_pages(match, [])
    assert "Échantillon limité" in pages[0].fields[0].value
    assert VIEWS.clock_ms(658000) == "10:58"


def test_match_buttons_and_navigation_have_unique_valid_ids():
    for button in (None, UI.make_open_button("EUW1_123", 5)):
        rows = VIEWS.make_match_buttons("EUW1_123", 5, button)
        assert len(rows[0].components) == (2 if button is None else 3)
        for component in rows[0].components[-2:]:
            assert VIEW_COG.OPEN_RE.fullmatch(component.custom_id)
    for kind in ("analysis", "progress"):
        for total in (1, 2, 13):
            for index in range(total):
                rows = VIEW_COG.page_components(kind, "EUW1_123", 5, index, total)
                buttons = rows[0].components
                ids = [b.custom_id for b in buttons]
                assert len(ids) == len(set(ids))
                assert all(len(i) <= 100 for i in ids)
                assert int(VIEW_COG.PAGE_RE.fullmatch(ids[0]).group(4)) == max(0, index - 1)
                assert int(VIEW_COG.PAGE_RE.fullmatch(ids[1]).group(4)) == min(total - 1, index + 1)


def test_match_view_callbacks_acknowledge_then_respond_and_handle_errors():
    old = VIEW_COG.load_pages
    try:
        pages = VIEWS.build_progress_pages(example_match(), [])
        VIEW_COG.load_pages = lambda *args: pages
        cog = VIEW_COG.LolMatchViews.__new__(VIEW_COG.LolMatchViews)
        for kind in ("analysis", "progress"):
            ctx = RecordingContext(f"lolview_open_{kind}_EUW1_123_5")
            asyncio.run(cog.on_open(ctx))
            assert ctx.calls[0] == ("defer", {"ephemeral": True})
            assert ctx.calls[-1][2]["embeds"] is pages[0]
            nav = RecordingContext(f"lolview_page_{kind}_EUW1_123_5_1_next")
            asyncio.run(cog.on_page(nav))
            assert nav.calls[0] == ("defer", {"edit_origin": True})
            assert nav.calls[-1][1]["embeds"] is pages[1]
        VIEW_COG.load_pages = lambda *args: None
        ctx = RecordingContext("lolview_open_analysis_EUW1_123_5")
        asyncio.run(cog.on_open(ctx))
        assert "plus disponibles" in ctx.calls[-1][1]
        def fail(*args):
            raise RuntimeError("DB unavailable")
        VIEW_COG.load_pages = fail
        asyncio.run(cog.on_open(ctx))
        assert "Impossible" in ctx.calls[-1][1]
        assert ctx.calls[-1][2]["components"] == []
    finally:
        VIEW_COG.load_pages = old


def test_match_view_timeout_returns_a_terminal_response():
    import time
    old_load, old_timeout = VIEW_COG.load_pages, VIEW_COG.LOAD_TIMEOUT
    try:
        VIEW_COG.load_pages = lambda *args: time.sleep(0.02)
        VIEW_COG.LOAD_TIMEOUT = 0.001
        ctx = RecordingContext("lolview_page_progress_EUW1_123_5_1_next")
        cog = VIEW_COG.LolMatchViews.__new__(VIEW_COG.LolMatchViews)
        asyncio.run(cog.on_page(ctx))
        assert ctx.calls[0] == ("defer", {"edit_origin": True})
        assert "trop de temps" in ctx.calls[-1][1]["content"]
    finally:
        VIEW_COG.load_pages, VIEW_COG.LOAD_TIMEOUT = old_load, old_timeout
