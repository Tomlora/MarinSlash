# Radar de compte LoL

`/lol_radar riot_id:MonPseudo riot_tag:EUW parties:20 mode:RANKED role:SUPPORT`

Compte enregistré dans `tracker` sur le serveur courant. Filtres optionnels : rôle,
champion et saison. RANKED par défaut, 1 à 100 parties (20 par défaut), toutes saisons
si aucune n'est précisée. Les filtres s'appliquent avant déduplication et limitation.
Les N derniers matchs distincts sont comparés aux N précédents, sans chevauchement.
Le nombre réel est affiché si l'historique est plus court. Le tag est obligatoire pour
distinguer deux comptes homonymes. Les modes hors Faille de l'invocateur sont exclus.

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
15 minutes et une timeline continue de 0 à 15 minutes (tolérance 1 seconde).
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

Sans snapshot radar, seuls KDA, KP et VSPM sont reconstruits depuis `matchs`.
La durée historique `mm.ss` est convertie en secondes pour la vision. Les autres
axes restent N/D jusqu'à l'enregistrement de nouveaux matchs ; aucun faux zéro
ni rétrocalcul de proximité depuis des positions sans santé. Les points manquants
interrompent le contour et empêchent le remplissage du polygone.

## Mise en service

1. Déployer les fichiers et redémarrer le bot pour charger le cog et synchroniser la commande.
2. Tester un compte suivi : vérifier les filtres et les effectifs. Un ancien historique
   doit afficher un radar partiel, y compris sans table `match_recap_details`.
3. Enregistrer une nouvelle partie d'au moins 15 minutes via le suivi habituel.
   Vérifier `data->'radar'` pour ce match et ce compte, puis relancer la commande.
4. Tester un ADC, un jungler, une partie courte et un compte sans historique.

SQL et Pillow s'exécutent hors de la boucle Discord ; le PNG est créé en mémoire
pour éviter les collisions de fichiers entre deux commandes simultanées.
