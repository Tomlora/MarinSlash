# Génération des récaps hors de la boucle Discord

Les commandes `/game`, `/game_rattrapage` et le tracker automatique passent par
`LeagueofLegends.printInfo()`. Cette méthode attend désormais un worker dédié
(`fonctions/match_worker.py`) pour construire le récap. La création de `MatchLol`,
les requêtes SQL, les analyses, les records, le rendu Pillow et l'enregistrement
de l'embed s'exécutent dans ce worker. Les appels HTTP du match utilisent une
boucle asyncio propre au job : leurs sessions ne traversent jamais les threads.

Les appels Discord et les challenges restent sur la boucle du bot. Les accès SQL
des challenges étaient déjà déportés dans des threads ; leurs verrous restent
ainsi partagés avec les commandes `/challenges`. Les lectures/écritures SQL autour
du pipeline (compte, paramètres, tracker, suivi de rang, relecture d'un récap) et
l'autocomplétion sont également exécutées hors de la boucle Discord.

Un seul match est construit à la fois : le code historique remplace certaines
tables de suivi et ne doit pas être exécuté concurremment. Une requête en attente
ne monopolise pas de thread. Chaque job utilise un répertoire temporaire distinct,
supprimé en cas de réussite comme d'erreur. Le PNG est envoyé depuis la mémoire ;
il n'existe plus de fichier partagé `resume.png` ou `resume_save.png` à supprimer
après l'envoi. Les boutons Records, Teamfight, Ganks, Détail du score, Différentiel
d'or et Challenges sont conservés.

Si l'appelant est annulé, un récap déjà demandé termine ses sauvegardes et son
nettoyage. Le compte reste marqué occupé jusqu'à la fin. Une annulation ne peut
pas interrompre sans risque une requête SQL synchrone en cours. Elle n'entraîne
pas d'envoi Discord ultérieur par le job. Les erreurs sont journalisées, même
si l'appelant n'attend plus le résultat. Le journal `fonctions.match_worker`
donne la durée de génération, hors attente dans la file et hors challenges.

## Vérification

`python -m pytest -q tests/test_match_async.py` vérifie notamment qu'un job bloqué
en synchrone laisse une tâche simulant les heartbeats progresser, que deux jobs
ne se chevauchent pas après annulation, que les fichiers et sessions sont nettoyés,
et que les vrais handlers `/game`, `printLive` et `update` gardent leur routage.
Les suites records/challenges vérifient les composants Discord et la persistance.

Cette isolation conserve le pilote SQL synchrone existant ; ce n'est pas une
migration globale du bot vers un pilote asynchrone. Les autres cogs qui créent
directement `MatchLol` ne passent pas automatiquement par ce worker. Un thread
partage encore le CPU et le GIL avec le bot : un traitement natif qui monopolise
le GIL ou une machine saturée peut encore produire de la latence. Une isolation
par processus pourra être envisagée si des mesures réelles l'exigent.

Après déploiement, comparer les alertes de heartbeat pendant `/game` et les
récaps automatiques avec les durées de génération. Les tests hors ligne ne
reproduisent ni les latences Riot/PostgreSQL de production, ni la charge du serveur.
