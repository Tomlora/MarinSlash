# Radar de compte LoL

`/lol_radar riot_id:MonPseudo` compare la saison en cours, configurée dans le bot,
à la saison précédente. Pour choisir une saison ou un rôle, par exemple,
utiliser `/lol_radar riot_id:MonPseudo saison:16 role:SUPPORT`.

Le bot recherche le tag dans les comptes suivis du serveur courant. En cas
d’homonymie, il affiche les tags possibles et demande de préciser `riot_tag`.
Le rôle et le champion sont facultatifs. Le SQL impose `mode = 'RANKED'`.
Tous les matchs distincts enregistrés de la saison choisie sont pris en compte,
sans limite de nombre de parties, et comparés à la saison précédente (S − 1).
Les mêmes filtres s'appliquent aux deux saisons avant déduplication. Les effectifs
réels figurent sous chaque moyenne. Un axe apparaît dès qu’une saison contient
une mesure. Un tiret indique que seule l’autre saison est renseignée. Quand la
saison précédente compte zéro partie, le tableau présente uniquement la saison choisie.
En dessous de trois axes renseignés, les moyennes sont présentées en tableau seul.

## Mesures (version 1)

Chaque valeur est une **moyenne des valeurs par match disponibles**, à poids égal.
`n` indique le nombre de matchs disponibles pour chaque axe et chaque période.
Il ne s'agit ni d'une somme de kills divisée par une somme de morts, ni d'une
comparaison à la population du serveur ou au classement Riot.

| Axe | Valeur par match | Plafond graphique |
|---|---|---|
| KDA | (kills + assists) / max(1, deaths) | 10 |
| KP% | 100 × (kills + assists) / kills de l'équipe | 100 % |
| VSPM | Vision score / durée réelle en minutes | 4 |
| FB% | 100 si premier sang obtenu **ou assisté**, 0 sinon | 100 % |
| K+A@15 | Kills + assists jusqu'à 15:00 inclus | 10 |
| KP@15 | Participation aux kills d'équipe jusqu'à 15:00 inclus | 100 % |
| Prox ADC | Part des relevés valides proches de l'ADC allié | 100 % |
| Prox JG | Part des relevés valides proches du jungler allié | 100 % |

Un dénominateur nul donne N/D. Les mesures à 15 minutes exigent un match d'au moins
15 minutes et une timeline continue jusqu’au premier relevé qui atteint ou dépasse
15:00 (écart maximal de 61 secondes entre relevés).
Les événements dupliqués ne comptent qu'une fois. Les exécutions ne sont pas
comptées comme des kills d'équipe.

Les proximités portent sur [2:00, 14:00), à distance ≤ 2 000 unités, avec les deux
joueurs vivants, à position/santé connue et hors des bases (rayon 2 500 autour des
deux coins). Les trous ne sont pas interpolés. La santé et la position ne permettent
pas de reconnaître tous les rappels en cours. C'est une estimation sur les relevés,
pas une durée de gank ni une détection de coopération. La proximité à soi-même est
N/D (ADC pour l'ADC, JG pour le jungler). Un rôle cible ambigu ou absent est N/D.

Le tracé utilise `min(100, 100 × valeur / plafond)` ; les valeurs brutes ne sont pas
plafonnées dans le tableau. Ces plafonds sont des repères fixes, **pas des percentiles**,
ni des objectifs optimaux. Une proximité plus forte n'est pas forcément meilleure.
Filtrer le même rôle est conseillé pour interpréter l'évolution.

## Stockage et anciens matchs

Le récap sauvegarde `data.radar` version 1 dans `match_recap_details`, identifié
par le PUUID du compte, depuis le détail Riot et la timeline déjà chargés. Aucun
appel Riot/UGG supplémentaire. Aucun changement de schéma : le JSONB existant est
réutilisé. La détection de table respecte le `search_path` PostgreSQL.

Les valeurs du snapshot radar sont prioritaires. Pour les champs manquants, le
bot consulte les données locales disponibles pour chaque match.

- KDA, KP et VSPM utilisent `matchs`, avec conversion de la durée historique `mm.ss`.
- FB% utilise les indicateurs de premier sang et d’assistance du scoring si le
  bénéficiaire du premier sang est enregistré et le compte identifiable par son Riot ID et son tag.
- K+A@15 utilise les éliminations et assistances dédupliquées de la timeline du compte.
  Leur total doit correspondre au bilan de fin de partie. Un événement horodaté à
  15:00 dans l’ancienne timeline arrondie rend la mesure incertaine. Un bilan final
  de zéro élimination et zéro assistance garantit zéro à 15 minutes si le match a duré jusque-là.
- KP@15 utilise aussi les éliminations alliées horodatées de la carte du récap,
  après vérification du total d’équipe sur toute la partie.
- Le récap de proximité jungle donne la distance du joueur à son jungler allié
  et, pour un jungler, celle à son ADC. Pour un ADC, la proximité à soi-même est inapplicable.

Les moyennes ne comptent que les observations disponibles, y compris les vrais zéros.
Les axes sans mesure dans les deux saisons sont nommés une seule fois en pied d’image.

## Mise en service

1. Déployer les fichiers et redémarrer le bot pour charger le cog et synchroniser la commande.
2. Tester un compte suivi : vérifier les filtres et les effectifs. Un ancien historique
   doit afficher un radar partiel, y compris sans table `match_recap_details`.
3. Enregistrer une nouvelle partie d'au moins 15 minutes via le suivi habituel.
   Vérifier `data->'radar'` pour ce match et ce compte, puis relancer la commande.
4. Tester un ADC, un jungler, une partie courte et un compte sans historique.

SQL et Pillow s'exécutent hors de la boucle Discord ; le PNG est créé en mémoire
pour éviter les collisions de fichiers entre deux commandes simultanées.
