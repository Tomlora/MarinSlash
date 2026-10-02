# Fantasy LoL — état de la branche fantasyleague

Le module est en développement dans la PR #26. Ce document décrit le code du
dépôt ; il ne remplace pas le README externe `Marin_Fantasy_LoL_README.md`, qui
n'a pas pu être consulté lors de cette reprise.

## Après la draft

- `/fantasy roster league_id:1` affiche ton roster de la saison courante,
  les identifiants des joueurs, leurs rôles et les championnats verrouillés.
- `/fantasy lineup league_id:1 joueur_id:6` titularise un joueur de ton banc
  au rôle enregistré dans le pool. Le titulaire précédent rejoint le banc.
- Le roster conserve cinq titulaires, trois remplaçants et une équipe ; les
  titulaires doivent représenter au moins deux championnats.
- Le championnat du joueur entrant **et** celui du sortant doivent être libres.
  Un match programmé, en cours ou terminé verrouille son championnat pendant
  toute sa date Europe/Paris. Un match annulé ou reporté ne le verrouille pas.
- Un joueur devenu inactif reste visible et peut être sorti du cinq titulaire,
  mais ne peut pas être titularisé. Son dernier championnat connu sert au lock.
- Seul le manager concerné peut changer son roster, sur le serveur de sa ligue,
  lorsque celle-ci est active. Les réponses sont privées.

Les changements et les deux intervalles d'historique sont écrits dans une seule
transaction. Une erreur annule tout. Un verrou de ligue sérialise les demandes
concurrentes ; des verrous PostgreSQL protègent les données du pool et du calendrier
pendant la validation. Les deux nouvelles commandes exécutent le SQL dans un
thread après avoir accusé réception de l'interaction Discord.

## Installation et vérification

Le schéma initial `sql/migrations/20260725_fantasy_initial.sql` suffit : aucune
migration supplémentaire pour les remplacements. Recharger l'extension
`cogs.fantasy_lol` et synchroniser les commandes Discord après mise à jour du bot.

Les locks reposent exclusivement sur le calendrier enregistré. Il faut encore
tenir `/fantasy_update_schedule` à jour manuellement ; un calendrier vide ou
incomplet ne garantit pas le verrouillage de tous les matchs réels.

```bash
python -m unittest discover -s tests -p 'test_fantasy*.py' -v
```

Sans `FANTASY_TEST_DSN`, les tests PostgreSQL sont explicitement ignorés.
Pour les lancer, fournir une base **jetable** nommée `marin_fantasy_test` : ces
tests réinitialisent son schéma `fantasy`. Ne jamais utiliser une base du bot.
Le workflow `Fantasy tests` crée cette base sur PostgreSQL 16 et utilise
Python 3.10, SQLAlchemy 2.0.4 et interactions.py 5.13.2.

## Prochaines étapes

1. Valider les providers sur les données réelles actuelles puis automatiser les
   synchronisations avec suivi de fraîcheur et traitement des indisponibilités.
2. Ajouter les agents libres et les échanges, avec propriété exclusive et locks.
3. Importer les résultats Oracle's Elixir et calculer les scores versionnés en
   utilisant le roster historique au moment des matchs.
4. Relier les périodes de confrontation aux scores, puis exposer le classement.

Le déploiement Discord et la validation des sources réelles restent distincts
des tests automatisés ; ce changement ne déploie pas le bot.
