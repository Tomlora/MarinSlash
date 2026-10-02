"""Embeds Discord natifs, lisibles sur mobile et sans fichier image partagé."""
import interactions
from datetime import datetime, timezone

from fonctions.challenge_progress import TIER_NAMES, clean, next_goal, number, objectives, visible

COLOR = 0x29B6A8
PAGE_SIZE = 5


def when(value):
    if not value:
        return 'Premier relevé'
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%d/%m/%Y à %H:%M UTC')
    except (TypeError, ValueError):
        return clean(value, 50)


def fmt(value):
    return f'{number(value):,.2f}'.rstrip('0').rstrip('.').replace(',', ' ')


def signed(value):
    return ('+' if value >= 0 else '−') + fmt(abs(value))


def bar(ratio):
    filled = min(10, max(0, int(ratio * 10)))
    return '▰' * filled + '▱' * (10 - filled)


def goal_text(goal):
    if not goal:
        return 'Aucun prochain seuil disponible.'
    return (f"{bar(goal['ratio'])} **{goal['ratio']:.0%}** du palier\n"
            f"Encore **{fmt(goal['remaining'])}** → **{TIER_NAMES[goal['tier']]}** "
            f"(seuil {fmt(goal['target'])})")


def entry_field(entry, evolution=False):
    name = ('⭐ ' if entry.get('favorite') else '') + clean(entry['name'], 100)
    name += f" · #{entry['id']}"
    lines = [clean(entry.get('description'), 240)]
    if evolution:
        lines.append(f"**{fmt(entry['before'])} → {fmt(entry['value'])}** ({signed(entry['delta'])})")
        if entry['level_delta']:
            icon = '🏅' if entry['level_delta'] > 0 else '↘'
            lines.append(f"{icon} {TIER_NAMES[entry['old_level']]} → **{TIER_NAMES[entry['level']]}**")
    else:
        lines.append(f"**{fmt(entry['value'])}** · {TIER_NAMES[entry['level']]}")
    lines.append(goal_text(entry.get('goal') or next_goal(entry)))
    if entry.get('position', 0) > 0:
        ranking = f"Classement Riot : **#{fmt(entry['position'])}**"
        if entry.get('rank_delta'):
            ranking += f" · {signed(entry['rank_delta'])} place(s)"
        lines.append(ranking)
    return name[:256], '\n'.join(filter(None, lines))[:1024]


def pages_for_entries(title, description, entries, evolution=False):
    pages = []
    for start in range(0, max(1, len(entries)), PAGE_SIZE):
        embed = interactions.Embed(title=title, description=description[:1500], color=COLOR)
        for entry in entries[start:start + PAGE_SIZE]:
            name, value = entry_field(entry, evolution)
            embed.add_field(name=name, value=value, inline=False)
        if not entries:
            embed.add_field(name='Rien à afficher', value='Aucun défi correspondant pour ce relevé.', inline=False)
        pages.append(embed)
    return pages


def finish(pages, footer):
    for index, page in enumerate(pages):
        page.set_footer(text=f'{index + 1}/{len(pages)} · {footer}'[:2048])
    return pages


def match_pages(snapshot, match_id):
    total = snapshot['total']
    delta = snapshot.get('points_delta')
    points = f"**{fmt(total.get('current'))} points**"
    if delta is not None:
        points += f' · **{signed(delta)}**'
    changes = snapshot['changes']
    promotions = sum(e['level_delta'] > 0 for e in changes)
    gains = sum(e['delta'] > 0 for e in changes)
    description = f"Match **{clean(match_id, 45)}**\n{points}\n🏅 **{promotions}** palier(s) franchi(s) · 📈 **{gains}** défi(s) en progrès"
    summary = interactions.Embed(title='✨ Challenges · Évolution', description=description, color=COLOR)
    if snapshot['baseline']:
        message = 'Premier relevé enregistré. Les évolutions seront disponibles aux prochains récaps.'
    elif not changes:
        message = 'Aucune évolution détectée parmi les défis affichés. Riot peut mettre certains compteurs à jour avec retard.'
    else:
        message = 'Paliers, progrès et mouvements de classement sont détaillés dans les pages suivantes.'
    summary.add_field(name='Le point sur tes défis', value=message, inline=False)
    summary.add_field(name='Période du relevé', value=(
        f"Depuis : {when(snapshot.get('since'))}\n"
        f"Observé : {when(snapshot['observed_at'])}\n"
        'Les compteurs Riot sont cumulés : cette évolution peut couvrir plusieurs parties.'), inline=False)
    pages = [summary]
    for title, entries in (
        ('🏅 Paliers franchis', [e for e in changes if e['level_delta'] > 0]),
        ('📈 Progression des défis', [e for e in changes if e['level_delta'] <= 0 and e['delta'] > 0]),
        ('↕ Classements et autres évolutions', [e for e in changes if e['level_delta'] <= 0 and e['delta'] <= 0]),
    ):
        if entries:
            pages.extend(pages_for_entries(title, f'Match {clean(match_id, 45)}', entries, True))
    pages.extend(pages_for_entries('🎯 Prochains objectifs', 'Favoris en premier, puis proximité du prochain palier.', snapshot['goals']))
    return finish(pages, 'Relevé sauvegardé · heures UTC')


def profile_pages(current, preferences, player_name, view='profil'):
    entries = visible(current['entries'], preferences)
    title = f"{clean(player_name, 65)} · Challenges"
    description = f"Relevé : {when(current['observed_at'])}"
    if view == 'objectifs':
        return finish(pages_for_entries('🎯 Objectifs · ' + title, description,
            objectives(current['entries'], preferences, limit=25)), 'Favoris puis proximité du palier')
    if view == 'best':
        entries = sorted((e for e in entries if e['position'] > 0), key=lambda e: e['position'])[:25]
        return finish(pages_for_entries('🏆 Meilleurs rangs · ' + title, description, entries), 'Classement Riot')
    total = current['total']
    summary = interactions.Embed(title='💠 ' + title, description=description +
        f"\n\n**{fmt(total.get('current'))} points** · {TIER_NAMES.get(total.get('level'), 'Non classé')}", color=COLOR)
    labels = {'TEAMWORK': "Travail d’équipe", 'EXPERTISE': 'Expertise', 'IMAGINATION': 'Imagination',
              'COLLECTION': 'Collection', 'VETERANCY': 'Vétérance'}
    for key, category in current.get('categories', {}).items():
        if key in labels:
            summary.add_field(name=labels[key], value=f"**{fmt(category.get('current'))} pts** · " +
                TIER_NAMES.get(category.get('level'), 'Non classé'), inline=True)
    favorites = [dict(e, favorite=True) for e in entries if e['id'] in preferences['favorites']]
    pages = [summary]
    if favorites:
        pages.extend(pages_for_entries('⭐ Défis suivis', description, favorites))
    pages.extend(pages_for_entries('🎯 À portée de main', description, objectives(current['entries'], preferences)))
    return finish(pages, 'Utilise /lol_challenges suivre pour choisir tes favoris')


def open_button(match_id, joueur, available=True):
    return interactions.Button(style=interactions.ButtonStyle.SECONDARY, label='Challenges', emoji='✨',
        custom_id=f'lolchal_open_{match_id}_{int(joueur)}', disabled=not available)


def recap_components(existing, match_id, joueur, available):
    """Ajouter Challenges sans remplacer les contrôles ni modifier les lignes reçues.

    Les vues MatchLoL fournissent déjà une liste d'ActionRow (jusqu'à six
    boutons avec les records). Discord impose au plus cinq boutons par ligne.
    """
    items = existing if isinstance(existing, (list, tuple)) else [existing]
    rows = []
    for item in items:
        if item is None:
            continue
        if isinstance(item, interactions.ActionRow):
            rows.append(interactions.ActionRow(*item.components))
        elif isinstance(item, interactions.Button):
            if rows and len(rows[-1].components) < 5 and all(
                isinstance(component, interactions.Button) for component in rows[-1].components
            ):
                rows[-1].components.append(item)
            else:
                rows.append(interactions.ActionRow(item))
        else:
            raise TypeError('Les contrôles du récap doivent être des boutons ou des ActionRow')
    button = open_button(match_id, joueur, available)
    for row in rows:
        for index, component in enumerate(row.components):
            if getattr(component, 'custom_id', None) == button.custom_id:
                row.components[index] = button
                return rows
    if rows and len(rows[-1].components) < 5 and all(
        isinstance(component, interactions.Button) for component in rows[-1].components
    ):
        rows[-1].components.append(button)
    else:
        if len(rows) >= 5:
            raise ValueError('Le récap utilise déjà les cinq lignes de composants Discord')
        rows.append(interactions.ActionRow(button))
    return rows


def page_components(key, joueur, page, total, kind='match'):
    return [interactions.ActionRow(
        interactions.Button(style=interactions.ButtonStyle.SECONDARY, label='Précédent',
            custom_id=f'lolchal_page_{kind}_{key}_{joueur}_{max(0, page-1)}', disabled=page == 0),
        interactions.Button(style=interactions.ButtonStyle.SECONDARY, label=f'{page+1}/{total}',
            custom_id='lolchal_indicator', disabled=True),
        interactions.Button(style=interactions.ButtonStyle.SECONDARY, label='Suivant',
            custom_id=f'lolchal_page_{kind}_{key}_{joueur}_{min(total-1, page+1)}', disabled=page == total-1))]
