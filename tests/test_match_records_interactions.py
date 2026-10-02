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


def test_challenges_are_added_to_all_existing_match_buttons():
    from fonctions.challenge_ui import recap_components

    for with_records in (False, True):
        record_button = UI.make_open_button('EUW1_123', 45) if with_records else None
        existing = VIEWS.make_match_buttons('EUW1_123', 45, record_button)
        original = [row.to_dict() for row in existing]
        for available in (False, True):
            rows = recap_components(existing, 'EUW1_123', 45, available)
            payload = [row.to_dict() for row in rows]
            before = [button for row in original for button in row['components']]
            after = [button for row in payload for button in row['components']]
            assert after[:-1] == before  # IDs, labels, styles et états intégralement conservés.
            assert [button['label'] for button in after[-6:]] == [
                '⚔️ Teamfight', '🌿 Ganks', '📊 Détail du score', '💰 Différentiel d’or', '🗺️ Carte de la partie', 'Challenges',
            ]
            assert after[-1]['disabled'] is not available
            assert [len(row['components']) for row in payload] == ([5, 2] if with_records else [5, 1])
            assert [row.to_dict() for row in existing] == original
            assert [row.to_dict() for row in recap_components(rows, 'EUW1_123', 45, available)] == payload
            # Les handlers des quatre vues restent enregistrés avec le même routage.
            for button in before[-5:-1]:
                assert VIEW_COG.OPEN_RE.fullmatch(button['custom_id'])
            assert before[-1]['custom_id'] == 'lolview_open_map_EUW1_123_45'


def test_reloaded_recap_sends_existing_views_and_challenges_together():
    """Exécuter le vrai handler de rejeu, en isolant les accès SQL/fichiers."""
    import ast
    import asyncio
    import __future__
    from unittest.mock import AsyncMock, Mock
    import pandas as pd
    from fonctions.challenge_ui import recap_components

    source = ast.parse((ROOT / 'cogs' / 'leagueoflegends.py').read_text(encoding='utf-8'))
    cls = next(node for node in source.body if isinstance(node, ast.ClassDef) and node.name == 'LeagueofLegends')
    handler = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'load_embed')
    handler.decorator_list = []
    module = ast.Module(body=[handler], type_ignores=[])
    snapshot = AsyncMock(return_value={'version': 1})
    record = types.SimpleNamespace(is_empty=lambda: False)
    for has_challenges in (True, False):
        snapshot.return_value = {'version': 1} if has_challenges else None
        ctx = types.SimpleNamespace(defer=AsyncMock(), send=AsyncMock())
        image = types.SimpleNamespace(save=Mock())
        namespace = {
            'asyncio': asyncio, 'interactions': interactions,
            'lire_bdd_perso': lambda *a, **kw: pd.DataFrame([{'joueur': 45, 'image': b'image', 'data': b'embed'}]).T,
            'Image': types.SimpleNamespace(open=lambda _: image),
            'io': types.SimpleNamespace(BytesIO=lambda value: value),
            'pickle': types.SimpleNamespace(loads=lambda _: interactions.Embed(title='Récap sauvegardé')),
            'os': types.SimpleNamespace(remove=Mock()),
            'traceback': types.SimpleNamespace(print_exc=Mock(side_effect=AssertionError('Rejeu en erreur'))),
            'load_account_preferences': lambda _: None,
            'load_record_snapshot': lambda *a: record,
            'add_featured_records': lambda *a, **kw: None,
            'filter_records': lambda *a: record,
            'make_open_button': UI.make_open_button,
            'load_match': lambda *a: {'match_id': 'EUW1_123'},
            'make_match_buttons': VIEWS.make_match_buttons,
            'recap_snapshot': snapshot, 'recap_components': recap_components,
        }
        exec(compile(module, '<real load_embed>', 'exec', flags=__future__.annotations.compiler_flag), namespace)
        asyncio.run(namespace['load_embed'](None, ctx, 'EUW1_123'))
        rows = ctx.send.call_args.kwargs['components']
        buttons = [button for row in rows for button in row.to_dict()['components']]
        assert len(buttons) == 7
        assert [button['custom_id'] for button in buttons] == [
            'lolrec_open_EUW1_123_45', 'lolview_open_teamfight_EUW1_123_45',
            'lolview_open_ganks_EUW1_123_45', 'lolview_open_score_EUW1_123_45',
            'lolview_open_gold_EUW1_123_45', 'lolview_open_map_EUW1_123_45', 'lolchal_open_EUW1_123_45',
        ]
        assert buttons[-1]['disabled'] is not has_challenges
        assert all(not button.get('disabled', False) for button in buttons[:-1])


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
    from matplotlib.collections import LineCollection
    original_save = Figure.savefig
    captured = {}
    def capture(figure, *args, **kwargs):
        ax = figure.axes[0]
        collection = next(c for c in ax.collections if isinstance(c, LineCollection))
        captured["segments"] = [s.tolist() for s in collection.get_segments()]
        captured["labels"] = [text.get_text() for text in ax.texts]
        captured["background"] = ax.get_facecolor()
        return original_save(figure, *args, **kwargs)
    with patch.object(Figure, "savefig", capture):
        png = DETAILS.render_gold(match, data["gold"])
    # Le compte est rouge : le différentiel bleu positif devient un retard allié.
    assert captured["segments"] == [[[0, 0], [1, -500]], [[1, -500], [2, -1000]]]
    assert captured["labels"] == ["+0", "-500", "-1 000", "-2 000"]
    assert captured["background"] == (1, 1, 1, 1)
    with Image.open(BytesIO(png)) as image:
        assert image.size == (1440, 660) and image.format == "PNG"
        assert len(image.convert("RGB").getcolors(maxcolors=1000000)) > 100
    file = interactions.File(BytesIO(png), file_name="gold_diff.png")
    assert file.file_name == "gold_diff.png"
    embed = DETAILS.gold_embed(match, data["gold"])
    assert embed.to_dict()["image"]["url"] == "attachment://gold_diff.png"
    assert "file" in inspect.signature(interactions.ComponentContext.send).parameters
    assert "attachments" in inspect.signature(interactions.ComponentContext.edit).parameters
    # Courbe à zéro et une seule minute : limites valides et PNG lisible.
    for points in ([{"minute": 0, "blue": 2500, "red": 2500}],
                   [{"minute": m, "blue": 2500, "red": 3500} for m in range(120)]):
        with Image.open(BytesIO(DETAILS.render_gold(match, points))) as image:
            assert image.width >= 1440 and image.height == 660


def test_close_uses_deferred_webhook_edit_and_removes_attachment():
    from unittest.mock import AsyncMock
    import asyncio

    http = types.SimpleNamespace(post_initial_response=AsyncMock(), edit_interaction_message=AsyncMock(return_value=None))
    client = types.SimpleNamespace(http=http, app=types.SimpleNamespace(id=123))
    ctx = types.SimpleNamespace(client=client, token="test-token", id=456, deferred=False, responded=False)
    # Vraies méthodes SDK, seul le transport HTTP est simulé.
    ctx.defer = types.MethodType(interactions.ComponentContext.defer, ctx)
    ctx._defer = types.MethodType(interactions.ComponentContext._defer, ctx)
    ctx.edit = types.MethodType(interactions.ComponentContext.edit, ctx)
    cog = types.SimpleNamespace()
    asyncio.run(VIEW_COG.LolMatchViews.on_close.callback(cog, ctx))
    assert http.post_initial_response.await_count == 1
    assert http.edit_interaction_message.await_count == 1
    payload = http.edit_interaction_message.call_args.kwargs["payload"]
    assert payload["attachments"] == []
    assert payload["components"] == []
    assert payload["embeds"] == []
