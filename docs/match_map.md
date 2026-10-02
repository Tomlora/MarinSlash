# Carte des dix joueurs dans le récap

Le bouton **Carte de la partie** ouvre une réponse privée. Les boutons existants
(Records, Teamfight, Ganks, Détail du score, Différentiel d'or, Challenges) restent
disponibles, répartis sur deux lignes si nécessaire.

- **Morts** : une carte par joueur, positions numérotées, horaires et champion
  responsable dans la légende. Une mort sans coordonnées reste dans la légende.
- **Déplacements** : positions relevées par Riot, environ chaque minute, numérotées
  chronologiquement. Aucun trait ne prétend reconstituer le trajet entre deux relevés.
- Sélection multiple de **1 à 10 joueurs**, raccourcis **Les 10 joueurs**, **Équipe
  bleue**, **Équipe rouge**. Choisir moins de joueurs agrandit les cartes.
- Fenêtres de **5 minutes**, navigation précédente/suivante, filtre conservé au
  changement de vue et de période. Les numéros de joueur et les couleurs d'équipe
  sont stables. Les étiquettes superposées sont décalées avec un repère vers leur
  position exacte.

## Données et compatibilité

`match_recap_details.data.map` contient un snapshot versionné des dix identités Riot,
des positions horodatées et des événements `CHAMPION_KILL` (y compris la dernière
frame partielle). Les `participantId` et `teamId` du match sont utilisés directement,
indépendamment des index réordonnés pour le scoring. La timeline déjà téléchargée
est réutilisée : **aucun nouvel appel Riot**, au récap ou au clic.

La carte utilise le fond existant `img/map2.jpg`, schématique, et accepte uniquement
la Faille de l'invocateur (`mapId=11`) avec dix participants, cinq par équipe.
Les récaps anciens sans snapshot et les autres cartes affichent une explication,
sans tenter de reconstruire les dix joueurs depuis les anciennes données du seul
compte suivi. Les trous restent des trous ; les relevés à une frontière sont visibles
sur les deux périodes voisines, mais les morts ne sont pas comptées deux fois.

Le stockage utilise la table JSONB existante, sans migration supplémentaire. La
sauvegarde est optionnelle et son échec ne bloque pas le récap. Le nouveau cog est
chargé par le chargement automatique des extensions au démarrage.

## Exécution et validation

L'interaction est acquittée avant toute lecture SQL. Lecture et rendu Pillow sont
exécutés hors de la boucle Discord. Un seul rendu peut être actif par instance du
cog ; les clics pendant un rendu reçoivent un message invitant à réessayer, sans
accumulation de jobs. Le délai de réponse de 15 secondes n'annule pas le thread :
celui-ci reste suivi jusqu'à son terme. Un accès SQL bloqué doit donc être résolu
au niveau de la connexion ; le timeout ne garantit pas son interruption.

Les filtres vivent dans les identifiants de composants, sans session mémoire
nécessaire après un redémarrage. Chaque modification remplace la pièce jointe via
`ctx.edit(attachments=[], file=...)`, compatible avec interactions.py 5.13.2.

Tests : `tests/test_match_map.py`, tests de non-régression du récap et round-trip
PostgreSQL dans `tests/test_match_records_database.py`. Le workflow records exécute
les tests SQL sur sa base jetable. La vérification dans un vrai serveur Discord
reste à réaliser après déploiement.
