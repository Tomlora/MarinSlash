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
   Les annotations chiffrées suivent un palier de `ceil(dernière minute / 5)` :
   toutes les 5 minutes pour 25 minutes, 6 pour 30, etc. Seules les minutes
   mesurées sont annotées, sans reconstitution des valeurs absentes.
3. **Or de chaque joueur** : un seul graphique avec les dix courbes. Chaque
   joueur a sa couleur ; les alliés sont en traits pleins avec cercles, les
   adversaires en tirets avec triangles. La légende sous le graphique regroupe
   les alliés puis les adversaires et indique poste, champion, nom et dernier relevé.
   La vue par défaut **Écart au joueur suivi** retire l'or du compte suivi à
   chaque minute : sa courbe noire est à zéro, les autres affichent leur avance
   ou retard. Cela retire la progression commune des totaux pour mieux distinguer
   les écarts. Le bouton **Or total** retrouve les courbes cumulées sur la même page.

Pour la vue des écarts, on calcule exactement `or_joueur(t) - or_suivi(t)`.
La distance verticale entre deux joueurs reste leur différence d'or. Seules les
minutes communes sont comparées ; si le relevé du joueur de référence manque,
les dix courbes sont interrompues à cette minute. L'identité de référence est
sauvegardée par PUUID ; pour un ancien snapshot, l'index Riot original est accepté
uniquement s'il désigne un joueur de l'équipe suivie. Une référence inconnue est
signalée, avec accès à Or total. Aucune valeur n'est reconstituée.

Les deux nouveaux PNG ont une résolution de 1690 × 1820 et 2080 × 1300 pixels.
Les annotations par poste sont espacées et la légende des dix joueurs reste hors des courbes. Les graduations
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
le basculement Écart au joueur suivi / Or total, un compte côté rouge, une partie
longue et un ancien récap. Comparer la première
image à l'ancien affichage. Les tests locaux ne valident pas le rendu du client Discord.
