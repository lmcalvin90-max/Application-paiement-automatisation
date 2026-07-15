# Application de Paiement Marchand — Sujet 3

Application DevOps clé en main : encaissement en caisse, validation métier stricte, persistance PostgreSQL, reverse proxy Nginx, et pipeline CI/CD GitHub Actions.

## Architecture

```
                        ┌────────────────────┐
   Navigateur  ───────► │  Nginx (port 80)   │   reverse proxy + en-têtes de sécurité
                        └─────────┬──────────┘
                                  │ http://api:5000
                                  ▼
                        ┌────────────────────┐
                        │  Flask API (5000)  │   validation métier, gunicorn
                        └─────────┬──────────┘
                                  │ psycopg2 :5432
                                  ▼
                        ┌────────────────────┐
                        │ PostgreSQL (5432)  │   table `transactions`
                        └────────────────────┘

Réseaux Docker :
  frontend (nginx <-> api)         backend (api <-> db, interne, non exposé)
```

## Règles métier (Sujet 3)

- **Caisse (`caisse_id`)** : obligatoire, doit appartenir à `['CAISSE_01', 'CAISSE_02', 'CAISSE_03']`.
- **Nom du client** : obligatoire.
- **Téléphone** : optionnel, format international si fourni (ex. `+33612345678`).
- **E-mail** : optionnel, format email standard si fourni.
- **Montant** : numérique, strictement supérieur à 0.
- **Canal de contact** : téléphone OU e-mail valide obligatoire (au moins un des deux).
- **Référence de transaction** : UUID v4 généré côté serveur et persisté en base.

## Démarrage en local

Prérequis : Docker et Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

L'application est ensuite accessible sur **http://localhost**.

Services démarrés :
- `db` — PostgreSQL 15 (volume persistant `postgres_data`, healthcheck `pg_isready`)
- `api` — API Flask (gunicorn, attend que `db` soit `service_healthy`)
- `nginx` — reverse proxy exposé sur le port 80

Pour arrêter :

```bash
docker compose down
```

Pour repartir d'une base vide :

```bash
docker compose down -v
```

## Endpoints de l'API

| Méthode | Route            | Description                                      |
|---------|-------------------|---------------------------------------------------|
| GET     | `/`               | Sert l'interface web                              |
| POST    | `/api/payment`    | Enregistre une transaction (validation stricte)   |
| GET     | `/api/payments`   | Liste toutes les transactions enregistrées        |
| GET     | `/health`         | État de santé du backend et de la connexion BDD   |

Exemple de requête :

```bash
curl -X POST http://localhost/api/payment \
  -H "Content-Type: application/json" \
  -d '{"caisse_id":"CAISSE_01","nom_client":"Jean Dupont","email":"jean@exemple.com","montant":49.99}'
```

## Exécuter les tests en local

Les tests utilisent SQLite en mémoire — aucune base PostgreSQL requise.

```bash
cd app
pip install -r requirements.txt
pip install pytest pytest-cov flake8
cd ..
pytest --cov=app tests/
```

Lint :

```bash
flake8 app tests --max-line-length=120
```

## Pipeline CI/CD

Le workflow `.github/workflows/ci.yml` s'exécute sur `push` et `pull_request` vers `main` et `develop`, en trois étapes séquentielles :

1. **Lint** — `flake8` sur `app/` et `tests/`.
2. **Tests** — `pytest --cov=app tests/` (base SQLite en mémoire).
3. **Docker Build** — construction de l'image API et de l'image Nginx pour valider les Dockerfiles.

## Sécurité (PCI-DSS / ISO 27001)

- Conteneur API exécuté avec un utilisateur non-root dédié.
- Build multi-stage réduisant la surface d'attaque de l'image finale.
- Cloisonnement réseau : le réseau `backend` (api ↔ db) est interne et non routable depuis l'extérieur ; seul `nginx` est exposé publiquement.
- En-têtes de sécurité HTTP (`X-Frame-Options`, `X-Content-Type-Options`) ajoutés par Nginx.
- Secrets (identifiants BDD) fournis via `.env`, exclu du dépôt Git par `.gitignore`.

## Équipe (factice)

- Camille Martin — DevOps Lead
- Sofia Nguyen — Backend Flask
- Younes El Amrani — Frontend & QA
- Léa Bertrand — Sécurité & CI/CD
