"""
Application de paiement marchand - API Flask
Sujet 3 - TP DevOps

Expose:
  GET  /            -> Interface web (index.html)
  POST /api/payment -> Enregistrement d'une transaction de paiement
  GET  /api/payments-> Liste des transactions enregistrees
  GET  /health       -> Etat de sante du backend + BDD
"""

import os
import re
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOX_IDS_VALIDES = ["CAISSE_01", "CAISSE_02", "CAISSE_03"]

# Regex email standard (RFC-simplifiee, suffisante pour validation applicative)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Regex telephone au format international standard (ex: +33612345678)
TELEPHONE_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")

DEFAULT_DATABASE_URL = (
    "postgresql://postgres:postgres@localhost:5432/paiement_marchand"
)


def build_database_url():
    """Construit l'URL de connexion PostgreSQL depuis les variables d'env."""
    explicit_url = os.environ.get("DATABASE_URL")
    if explicit_url:
        return explicit_url

    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    host = os.environ.get("POSTGRES_HOST", "db")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db_name = os.environ.get("POSTGRES_DB", "paiement_marchand")
    return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = build_database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
    }

    db.init_app(app)
    return app


db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Modele de donnees
# ---------------------------------------------------------------------------

class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    caisse_id = db.Column(db.String(50), nullable=False)
    nom_client = db.Column(db.String(255), nullable=False)
    telephone = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    montant = db.Column(db.Float, nullable=False)
    ref_transaction = db.Column(db.String(36), nullable=False, unique=True)
    date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "caisse_id": self.caisse_id,
            "nom_client": self.nom_client,
            "telephone": self.telephone,
            "email": self.email,
            "montant": self.montant,
            "ref_transaction": self.ref_transaction,
            "date": self.date.isoformat() if self.date else None,
        }


# ---------------------------------------------------------------------------
# Validation metier
# ---------------------------------------------------------------------------

def valider_paiement(data):
    """
    Valide les regles metier du Sujet 3 (paiement marchand).
    Retourne (erreurs: list[str], valeurs_nettoyees: dict)
    """
    erreurs = []

    if not isinstance(data, dict):
        return ["Le corps de la requete doit etre un objet JSON valide."], {}

    caisse_id = (data.get("caisse_id") or "").strip()
    nom_client = (data.get("nom_client") or "").strip()
    telephone = (data.get("telephone") or "").strip() or None
    email = (data.get("email") or "").strip() or None
    montant = data.get("montant")

    # Caisse
    if not caisse_id:
        erreurs.append("L'identifiant de la caisse (caisse_id) est obligatoire.")
    elif caisse_id not in BOX_IDS_VALIDES:
        erreurs.append(
            f"Identifiant de caisse invalide '{caisse_id}'. Valeurs autorisees: {BOX_IDS_VALIDES}."
        )

    # Nom client
    if not nom_client:
        erreurs.append("Le nom du client est obligatoire.")

    # Telephone (optionnel mais regex si fourni)
    if telephone and not TELEPHONE_REGEX.match(telephone):
        erreurs.append(
            "Le format du telephone est invalide. Format attendu: international, ex. +33612345678."
        )

    # Email (optionnel mais regex si fourni)
    if email and not EMAIL_REGEX.match(email):
        erreurs.append("Le format de l'email est invalide.")

    # Montant
    if montant is None or isinstance(montant, bool):
        erreurs.append("Le montant est obligatoire et doit etre numerique.")
    else:
        try:
            montant = float(montant)
            if montant <= 0:
                erreurs.append("Le montant doit etre strictement superieur a 0.")
        except (TypeError, ValueError):
            erreurs.append("Le montant doit etre une valeur numerique valide.")
            montant = None

    # Canal de contact obligatoire : telephone OU email valide
    telephone_valide = bool(telephone and TELEPHONE_REGEX.match(telephone))
    email_valide = bool(email and EMAIL_REGEX.match(email))
    if not telephone_valide and not email_valide:
        erreurs.append(
            "Au moins un canal de contact valide (telephone ou email) doit etre fourni."
        )

    valeurs = {
        "caisse_id": caisse_id,
        "nom_client": nom_client,
        "telephone": telephone,
        "email": email,
        "montant": montant,
    }

    return erreurs, valeurs


# ---------------------------------------------------------------------------
# Initialisation Flask + retry-loop de connexion PostgreSQL
# ---------------------------------------------------------------------------

app = create_app()


def attendre_bdd_et_creer_tables(max_tentatives=5, delai_secondes=3):
    """
    Mecanisme de retry-loop pour eviter que Flask ne crash si PostgreSQL
    n'a pas encore fini de demarrer lors du 'docker compose up'.
    """
    for tentative in range(1, max_tentatives + 1):
        try:
            with app.app_context():
                db.session.execute(text("SELECT 1"))
                db.create_all()
            print(f"[startup] Connexion PostgreSQL etablie (tentative {tentative}).")
            return True
        except OperationalError as exc:
            print(
                f"[startup] Tentative {tentative}/{max_tentatives} echouee : {exc}. "
                f"Nouvel essai dans {delai_secondes}s..."
            )
            time.sleep(delai_secondes)
        except Exception as exc:  # sécurité additionnelle, ex: DB pas encore résolue en DNS
            print(
                f"[startup] Tentative {tentative}/{max_tentatives} echouee (erreur inattendue) : {exc}. "
                f"Nouvel essai dans {delai_secondes}s..."
            )
            time.sleep(delai_secondes)

    print("[startup] Impossible de se connecter a PostgreSQL apres plusieurs tentatives.")
    return False


# On ne lance le retry-loop qu'en dehors des tests (les tests configurent leur propre BDD).
if os.environ.get("SKIP_DB_INIT") != "1":
    attendre_bdd_et_creer_tables()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/payment", methods=["POST"])
def creer_paiement():
    data = request.get_json(silent=True)
    erreurs, valeurs = valider_paiement(data)

    if erreurs:
        return jsonify({"success": False, "errors": erreurs}), 400

    ref_transaction = str(uuid.uuid4())

    transaction = Transaction(
        caisse_id=valeurs["caisse_id"],
        nom_client=valeurs["nom_client"],
        telephone=valeurs["telephone"],
        email=valeurs["email"],
        montant=valeurs["montant"],
        ref_transaction=ref_transaction,
    )

    db.session.add(transaction)
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "message": "Paiement enregistre avec succes.",
                "ref_transaction": ref_transaction,
                "transaction": transaction.to_dict(),
            }
        ),
        201,
    )


@app.route("/api/payments", methods=["GET"])
def lister_paiements():
    transactions = Transaction.query.order_by(Transaction.date.desc()).all()
    return jsonify({"success": True, "count": len(transactions), "transactions": [t.to_dict() for t in transactions]})


@app.route("/health", methods=["GET"])
def health():
    db_status = "ok"
    try:
        db.session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"erreur: {exc}"

    return jsonify(
        {
            "status": "ok",
            "database": db_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
