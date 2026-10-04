# Différentiel d'or : trois pages

Le bouton existant ouvre toujours une consultation privée, persistante après
redémarrage. Précédent / Suivant parcourt exactement trois pages :

1. **Graphique actuel** : même fonction `render_gold`, même image, mêmes données,
   couleurs et annotations. Seuls les contrôles et le pied de page deviennent
   ceux du paginator (1/3).
2. **Écart par poste** : cinq graphiques TOP, JUNGLE, MID, ADC et SUPP. Chaque
   courbe calcule l'or du joueur allié moins celui de son vis-à-vis à la même
   minute. Les noms/champions des deux joueurs et le dernier écart sont indiqués.
   Les cinq axes partagent les mêmes échelles, avec bleu positif et rouge négatif.
3. **Or de chaque joueur** : dix graphiques séparés en deux colonnes, alliés à
   gauche puis adversaires à droite, rangés par poste. Une courbe par joueur,
   avec nom, champion, dernier relevé et mêmes échelles sur les dix graphiques.

Les deux nouveaux PNG ont une résolution de 1690 × 1820 et 2080 × 1820 pixels,
sans superposition de dix courbes ni étiquettes à chaque minute. Les graduations
restent espacées même sur une partie longue ; les noms trop longs sont tronqués.
L'image peut être ouverte en grand dans Discord.

## Données

Snapshot versionné `gold_players` dans le JSONB `match_recap_details`, à côté de
`gold`, `map`, `players`, `scores` et `jungle_proximity`. Aucun appel Riot ajouté
et aucune migration. Les identités/équipes viennent de participantId, PUUID et
teamId natifs ; le poste vient de teamPosition, puis individualPosition.

Une minute entière accepte au maximum 1 000 ms de dérive de la frame, comme la
page historique. On conserve le relevé valide le plus proche pour chaque joueur.
La dernière frame partielle ne remplace pas une minute entière. L'or absent,
négatif ou non fini est exclu, le vrai zéro est conservé. Les trous restent des
interruptions ; la différence par poste utilise uniquement les minutes communes.

Un poste absent ou ambigu n'est pas apparié arbitrairement. Les courbes individuelles
restent disponibles même sans poste. Un ancien récap n'ayant que les totaux conserve
la page 1 ; les pages 2/3 expliquent qu'une réanalyse ou une nouvelle partie avec
timeline est nécessaire. Les totaux ne permettent pas de reconstruire l'or individuel.

## Interaction et vérification réelle

Le clic est acquitté avant SQL et rendu, exécutés en thread. Seule la page demandée
est rendue et le verrou Matplotlib existant est partagé. Chaque changement de page
remplace l'ancienne pièce jointe via `ctx.edit(attachments=[])`, y compris quand
le graphique suivant est absent ou si le chargement échoue.

Après déploiement, vérifier 1 → 2 → 3 → 2 → 1, les pièces jointes, Fermer,
un compte côté rouge, une partie longue et un ancien récap. Comparer la première
image à l'ancien affichage. Les tests locaux ne valident pas le rendu du client Discord.
