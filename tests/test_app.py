"""
Suite de tests pytest - Application de paiement marchand
Utilise une base SQLite en memoire pour executer les tests sans PostgreSQL
(compatible GitHub Actions runner sans service additionnel).
"""

import os
import re
import sys
import pytest

import app as app_module  # noqa: E402

os.environ["SKIP_DB_INIT"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    app_module.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app_module.app.app_context():
        app_module.db.create_all()

    with app_module.app.test_client() as test_client:
        yield test_client

    with app_module.app.app_context():
        app_module.db.drop_all()

PAIEMENT_VALIDE = {
    "caisse_id": "CAISSE_01",
    "nom_client": "Jean Dupont",
    "telephone": "+33612345678",
    "email": "jean.dupont@example.com",
    "montant": 49.99,
}

def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"

def test_index_route_sert_le_frontend(client):
    response = client.get("/")
    assert response.status_code == 200

def test_paiement_valide_reussit(client):
    response = client.post("/api/payment", json=PAIEMENT_VALIDE)
    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert "ref_transaction" in data

def test_caisse_invalide_est_rejetee(client):
    payload = dict(PAIEMENT_VALIDE, caisse_id="CAISSE_99")
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert any("caisse" in e.lower() for e in data["errors"])

def test_montant_negatif_est_rejete(client):
    payload = dict(PAIEMENT_VALIDE, montant=-10)
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert any("montant" in e.lower() for e in data["errors"])

def test_montant_zero_est_rejete(client):
    payload = dict(PAIEMENT_VALIDE, montant=0)
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert any("montant" in e.lower() for e in data["errors"])

def test_absence_totale_de_contact_est_rejetee(client):
    payload = dict(PAIEMENT_VALIDE, telephone=None, email=None)
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert any("contact" in e.lower() for e in data["errors"])

def test_email_invalide_est_rejete(client):
    payload = dict(PAIEMENT_VALIDE, email="pas-un-email")
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert any("email" in e.lower() for e in data["errors"])

def test_telephone_invalide_est_rejete(client):
    payload = dict(PAIEMENT_VALIDE, telephone="0612345678", email=None)
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert any("telephone" in e.lower() for e in data["errors"])

def test_paiement_valide_avec_seulement_email(client):
    payload = dict(PAIEMENT_VALIDE, telephone=None)
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 201

def test_paiement_valide_avec_seulement_telephone(client):
    payload = dict(PAIEMENT_VALIDE, email=None)
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 201

def test_reference_transaction_est_un_uuid_v4(client):
    response = client.post("/api/payment", json=PAIEMENT_VALIDE)
    data = response.get_json()
    ref = data["ref_transaction"]
    uuid_v4_regex = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    assert uuid_v4_regex.match(ref) is not None

def test_liste_des_paiements(client):
    client.post("/api/payment", json=PAIEMENT_VALIDE)
    response = client.get("/api/payments")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["count"] >= 1

def test_nom_client_obligatoire(client):
    payload = dict(PAIEMENT_VALIDE, nom_client="")
    response = client.post("/api/payment", json=payload)
    assert response.status_code == 400
    data = response.get_json()
    assert any("nom" in e.lower() for e in data["errors"])
