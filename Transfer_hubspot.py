"""
TRANSFER PLATFORM - Intégration HubSpot CRM
Crée automatiquement un contact HubSpot à chaque nouveau compte TRANSFER
Documentation: https://developers.hubspot.com/docs/api/crm/contacts
"""

import os
import requests

HUBSPOT_ACCESS_TOKEN = os.getenv('HUBSPOT_ACCESS_TOKEN', '')
HUBSPOT_ENABLED = bool(HUBSPOT_ACCESS_TOKEN)

HUBSPOT_BASE_URL = "https://api.hubapi.com"


def creer_contact(numero_mtn: str, nom: str, type_compte: str,
                   email: str = None) -> dict:
    """
    Crée un contact HubSpot pour un nouveau compte TRANSFER.
    Le numéro MTN est stocké dans un champ personnalisé phone,
    et le type de compte (AGENT/CLIENT) dans une propriété custom si elle existe.
    """
    if not HUBSPOT_ENABLED:
        print("⚠️ HubSpot désactivé (HUBSPOT_ACCESS_TOKEN manquant)")
        return {"success": False, "reason": "not_configured"}

    # Sépare le nom en prénom/nom si possible (simplifié)
    parts = nom.strip().split(" ", 1)
    firstname = parts[0]
    lastname = parts[1] if len(parts) > 1 else ""

    properties = {
        "firstname": firstname,
        "lastname": lastname,
        "phone": numero_mtn,
        "hs_lead_status": "NEW",
        "lifecyclestage": "customer"
    }

    if email:
        properties["email"] = email

    try:
        response = requests.post(
            f"{HUBSPOT_BASE_URL}/crm/v3/objects/contacts",
            headers={
                "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"properties": properties},
            timeout=10
        )

        if response.status_code == 201:
            contact_id = response.json().get("id")
            print(f"✅ Contact HubSpot créé: {contact_id} ({nom})")
            return {"success": True, "contact_id": contact_id}

        elif response.status_code == 409:
            # Contact déjà existant (même email ou téléphone) — pas une erreur bloquante
            print(f"ℹ️ Contact HubSpot déjà existant pour {nom}")
            return {"success": True, "already_exists": True}

        else:
            print(f"❌ Erreur HubSpot ({response.status_code}): {response.text}")
            return {"success": False, "reason": response.text}

    except Exception as e:
        print(f"❌ Erreur connexion HubSpot: {e}")
        return {"success": False, "reason": str(e)}
