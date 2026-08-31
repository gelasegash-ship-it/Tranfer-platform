"""
TRANSFER PLATFORM - Intégration MTN Mobile Money (MoMo API)
Collection (recevoir de l'argent) + Disbursement (envoyer de l'argent)
Documentation: https://momodeveloper.mtn.com
"""

import os
import uuid
import requests
import base64

MTN_SUBSCRIPTION_KEY_COLLECTION = os.getenv('MTN_SUBSCRIPTION_KEY_COLLECTION', '')
MTN_SUBSCRIPTION_KEY_DISBURSEMENT = os.getenv('MTN_SUBSCRIPTION_KEY_DISBURSEMENT', '')
MTN_API_USER = os.getenv('MTN_API_USER', '')
MTN_API_KEY = os.getenv('MTN_API_KEY_SECRET', '')
MTN_ENVIRONMENT = os.getenv('MTN_ENVIRONMENT', 'sandbox')  # 'sandbox' ou 'mtncongo' (prod)
MTN_CALLBACK_HOST = os.getenv('MTN_CALLBACK_HOST', 'https://tranfer-platform-api.onrender.com')

MTN_ENABLED = bool(MTN_SUBSCRIPTION_KEY_COLLECTION and MTN_API_USER and MTN_API_KEY)

MTN_BASE_URL = (
    "https://sandbox.momodeveloper.mtn.com" if MTN_ENVIRONMENT == "sandbox"
    else "https://proxy.momoapi.mtn.com"
)


def _obtenir_token(subscription_key: str, product: str) -> str:
    """Récupère un token d'accès OAuth2 pour un produit MTN donné (collection/disbursement)"""
    if not MTN_ENABLED:
        raise RuntimeError("MTN Mobile Money non configuré (variables MTN_* manquantes)")

    credentials = base64.b64encode(f"{MTN_API_USER}:{MTN_API_KEY}".encode()).decode()

    response = requests.post(
        f"{MTN_BASE_URL}/{product}/token/",
        headers={
            "Authorization": f"Basic {credentials}",
            "Ocp-Apim-Subscription-Key": subscription_key
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()["access_token"]


def demander_paiement(numero_mtn_client: str, montant: float, devise: str = "XAF",
                       reference_externe: str = None) -> dict:
    """
    Demande un paiement (Collection) : le client reçoit une notification MTN
    sur son téléphone pour approuver le paiement vers TRANSFER.
    """
    token = _obtenir_token(MTN_SUBSCRIPTION_KEY_COLLECTION, "collection")
    reference_id = str(uuid.uuid4())

    response = requests.post(
        f"{MTN_BASE_URL}/collection/v1_0/requesttopay",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": MTN_ENVIRONMENT,
            "Ocp-Apim-Subscription-Key": MTN_SUBSCRIPTION_KEY_COLLECTION,
            "Content-Type": "application/json"
        },
        json={
            "amount": str(montant),
            "currency": devise,
            "externalId": reference_externe or reference_id,
            "payer": {"partyIdType": "MSISDN", "partyId": numero_mtn_client},
            "payerMessage": "Rechargement TRANSFER Platform",
            "payeeNote": "Rechargement compte"
        },
        timeout=10
    )
    response.raise_for_status()

    return {"reference_id": reference_id, "status": "PENDING"}


def verifier_statut_paiement(reference_id: str) -> dict:
    """Vérifie le statut d'une demande de paiement (SUCCESSFUL / FAILED / PENDING)"""
    token = _obtenir_token(MTN_SUBSCRIPTION_KEY_COLLECTION, "collection")

    response = requests.get(
        f"{MTN_BASE_URL}/collection/v1_0/requesttopay/{reference_id}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Target-Environment": MTN_ENVIRONMENT,
            "Ocp-Apim-Subscription-Key": MTN_SUBSCRIPTION_KEY_COLLECTION
        },
        timeout=10
    )
    response.raise_for_status()
    return response.json()


def envoyer_argent(numero_mtn_beneficiaire: str, montant: float, devise: str = "XAF",
                    reference_externe: str = None) -> dict:
    """
    Envoie de l'argent (Disbursement) : crédite directement le compte MTN Mobile Money
    d'un bénéficiaire, sans qu'il ait besoin d'approuver (utilisé pour les retraits).
    """
    token = _obtenir_token(MTN_SUBSCRIPTION_KEY_DISBURSEMENT, "disbursement")
    reference_id = str(uuid.uuid4())

    response = requests.post(
        f"{MTN_BASE_URL}/disbursement/v1_0/transfer",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Reference-Id": reference_id,
            "X-Target-Environment": MTN_ENVIRONMENT,
            "Ocp-Apim-Subscription-Key": MTN_SUBSCRIPTION_KEY_DISBURSEMENT,
            "Content-Type": "application/json"
        },
        json={
            "amount": str(montant),
            "currency": devise,
            "externalId": reference_externe or reference_id,
            "payee": {"partyIdType": "MSISDN", "partyId": numero_mtn_beneficiaire},
            "payerMessage": "Retrait TRANSFER Platform",
            "payeeNote": "Retrait de fonds"
        },
        timeout=10
    )
    response.raise_for_status()

    return {"reference_id": reference_id, "status": "PENDING"}
