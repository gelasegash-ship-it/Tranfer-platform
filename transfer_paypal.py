"""
TRANSFER PLATFORM - Intégration PayPal réelle
Création de paiements (checkout) + vérification de webhook signée
"""

import os
import requests

PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET', '')
PAYPAL_WEBHOOK_ID = os.getenv('PAYPAL_WEBHOOK_ID', '')
PAYPAL_MODE = os.getenv('PAYPAL_MODE', 'sandbox')  # 'sandbox' ou 'live'
PAYPAL_ENABLED = bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET)

PAYPAL_BASE_URL = (
    "https://api-m.paypal.com" if PAYPAL_MODE == "live"
    else "https://api-m.sandbox.paypal.com"
)


def obtenir_access_token() -> str:
    """Récupère un token OAuth2 PayPal (valable ~9h, à ne pas re-demander à chaque appel en prod)"""
    if not PAYPAL_ENABLED:
        raise RuntimeError("PayPal non configuré (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET manquants)")

    response = requests.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
        timeout=10
    )
    response.raise_for_status()
    return response.json()["access_token"]


def creer_paiement_paypal(montant: float, devise: str, numero_mtn: str,
                           description: str = "Rechargement TRANSFER") -> dict:
    """
    Crée un ordre de paiement PayPal (checkout).
    Le numero_mtn est stocké en custom_id pour identifier le compte à créditer
    quand le webhook confirmera le paiement.
    """
    token = obtenir_access_token()

    response = requests.post(
        f"{PAYPAL_BASE_URL}/v2/checkout/orders",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        json={
            "intent": "CAPTURE",
            "purchase_units": [{
                "amount": {"currency_code": devise, "value": f"{montant:.2f}"},
                "description": description,
                "custom_id": numero_mtn
            }]
        },
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    lien_approbation = next(
        (link["href"] for link in data.get("links", []) if link["rel"] == "approve"),
        None
    )

    return {
        "order_id": data["id"],
        "status": data["status"],
        "approve_url": lien_approbation
    }


def capturer_paiement(order_id: str) -> dict:
    """Capture (finalise) un paiement PayPal approuvé par l'utilisateur"""
    token = obtenir_access_token()

    response = requests.post(
        f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def verifier_signature_webhook(headers: dict, body: bytes) -> bool:
    """
    Vérifie qu'un webhook PayPal reçu est authentique (pas falsifié)
    via l'API officielle de vérification de PayPal.
    """
    if not PAYPAL_WEBHOOK_ID:
        print("⚠️ PAYPAL_WEBHOOK_ID non configuré — vérification de signature impossible")
        return False

    try:
        token = obtenir_access_token()
        import json

        verification_payload = {
            "auth_algo": headers.get("paypal-auth-algo"),
            "cert_url": headers.get("paypal-cert-url"),
            "transmission_id": headers.get("paypal-transmission-id"),
            "transmission_sig": headers.get("paypal-transmission-sig"),
            "transmission_time": headers.get("paypal-transmission-time"),
            "webhook_id": PAYPAL_WEBHOOK_ID,
            "webhook_event": json.loads(body)
        }

        response = requests.post(
            f"{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=verification_payload,
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("verification_status") == "SUCCESS"

    except Exception as e:
        print(f"❌ Erreur vérification webhook PayPal: {e}")
        return False
