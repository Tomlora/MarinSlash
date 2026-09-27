# Challenges : objectifs, favoris et évolution depuis un récap

Le bouton **Challenges**, ajouté aux contrôles MatchLoL existants (records,
Teamfight, Ganks, Détail du score, Différentiel d’or), ouvre un embed privé
avec navigation : aperçu, paliers franchis, progrès, classements/autres évolutions,
puis objectifs proches. Les défis sans rang Riot sont également affichés.
Chaque page contient au plus cinq défis. Aucun fichier image temporaire n'est utilisé.
Les cinq boutons existants restent sur la première ligne; Challenges occupe une
deuxième ligne lorsque les records sont présents. Sans bouton de records, les
quatre vues et Challenges tiennent sur une ligne. Cette composition s'applique
aux nouveaux récaps comme aux récaps sauvegardés rechargés.

## Commandes

Toutes les commandes sont sous `/lol_challenges`, sur le serveur du compte suivi.

| Commande | Usage |
| --- | --- |
| `profil` | Points, catégories, favoris et cinq objectifs |
| `objectifs` | Jusqu'à 25 objectifs actifs, favoris puis proximité du palier |
| `catalogue` | Recherche par nom ou description dans les défis connus du compte |
| `suivre` | Ajouter/retirer un favori ou exclure/réinclure un défi par nom ou ID |
| `preferences` | Voir les favoris et exclusions, y compris globales |
| `best` | Les 25 meilleurs rangs Riot |
| `classement` | Les 20 meilleurs scores de challenges du serveur |
| `historique` | Détails des dix derniers récaps enregistrés |
| `manage` | Exclusion/réinclusion globale par ID, propriétaires du bot uniquement |
| `help` | Aide intégrée |

Les options joueur sont `riot_id` et `riot_tag` (obligatoire en cas d'ambiguïté).
Seul le propriétaire Discord du compte peut modifier ses préférences personnelles.
`tracker` est remplacée par `suivre`. Le classement camembert et les images de profil
sont remplacés par des embeds. L'option `nb_challenges` du tracker est retirée :
le détail est désormais paginé et ne tronque pas les évolutions.

## Collecte et précision

Activer `tracker_challenges` dans `/lol_compte modifier_parametres` pour enregistrer
un relevé lors des prochains récaps automatiques. Les autres comptes actifs sont
actualisés par la tâche quotidienne de 6 h (horloge existante du planificateur).
Le premier accès à un profil sans relevé initialise sa référence.
Les consultations suivantes ne modifient pas cette référence.

L'API Riot renvoie l'état **cumulé** des challenges, pas leurs événements par match.
L'interface indique donc la période entre deux relevés et avertit qu'elle peut
couvrir plusieurs parties ou des mises à jour tardives. Un premier relevé ou un
nouveau défi n'est jamais présenté comme un gain depuis zéro.
Les promotions sont distinguées des baisses/corrections. Le prochain palier utilise
l'ordre explicite des niveaux et les seuils présents, y compris depuis `NONE`.

Le récap enregistre une copie immuable des évolutions et objectifs **avant** d'envoyer
le message. Les clics ne font aucun appel Riot et fonctionnent après redémarrage.
Rejouer un match déjà enregistré ne remplace ni son détail ni la référence courante.
Les récaps manuels et les anciennes parties consultent uniquement le détail existant;
ils n'inventent pas d'évolution à partir de l'état actuel. Un bouton grisé signifie
que le relevé est indisponible (ancien match, suivi désactivé, collecte en échec).
Les préférences nouvelles ne réécrivent pas les anciens récaps.

## Déploiement et données

Les trois tables PostgreSQL `challenge_accounts`, `match_challenges` et
`challenge_preferences` et l'index d'historique sont créés automatiquement au premier
accès. Le compte SQL doit avoir les droits CREATE TABLE/INDEX. Les anciens IDs
d'exclusion de `challenge_exclusion` sont importés sans écraser les nouvelles préférences.
Les exclusions globales (`joueur=-1`) restent prioritaires.
Les anciennes tables `challenges*` ne sont ni supprimées ni modifiées; les nouveaux
relevés repartent d'une référence explicite, sans interpréter les anciennes données
comme un historique par match. Aucun backfill de progression n'est possible sans relevés.

La sauvegarde du détail et de la référence est transactionnelle avec verrou par compte.
Une erreur annule les deux écritures. Le catalogue Riot est mis en cache six heures.
Les accès SQL sont exécutés hors de la boucle asyncio; appels réseau et interactions
ont des délais bornés. Une erreur de collecte laisse le récap principal publiable et
conserve la référence précédente. Les clés Riot transitent dans un en-tête HTTP.

Les sessions de commandes expirent après 15 minutes (256 maximum). Le détail des
matchs est conservé en base sans expiration automatique; prévoir la politique de
rétention selon la taille du tracker. La tâche quotidienne ne consomme pas les
évolutions des comptes suivis en live, sauf leur initialisation si aucun relevé n'existe.

## Validation

```sh
python -m pytest -q tests/test_challenges.py tests/test_match_records_ui.py tests/test_match_records_interactions.py
```

Le workflow `test-challenges.yml` ajoute PostgreSQL 16 pour vérifier rollback,
idempotence, concurrence, migration et rejets de relevés obsolètes. Pour le lancer
localement, définir `CHALLENGES_TEST_DATABASE_URL` vers une base **challenges_test**
jetable, puis exécuter `tests/test_challenges_postgres.py`. Ces tests recréent leurs
tables dans cette base dédiée uniquement. Aucun token Riot/Discord n'est nécessaire.
