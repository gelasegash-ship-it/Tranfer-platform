"""
TRANSFER PLATFORM - Notifications SMS via Twilio
Envoie un SMS de confirmation à chaque transaction (transfert, retrait, dépôt)
"""

import os
from datetime import datetime

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')
SMS_ENABLED = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)

if SMS_ENABLED:
    from twilio.rest import Client
    _client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def format_numero_e164(numero: str) -> str:
    """Convertit un numéro local en format international E.164 (ex: 243777000000 -> +243777000000)"""
    numero = numero.strip().replace(" ", "")
    if numero.startswith("+"):
        return numero
    return f"+{numero}"


def envoyer_sms(numero_destinataire: str, message: str) -> bool:
    """Envoie un SMS via Twilio"""
    if not SMS_ENABLED:
        print("⚠️ Notifications SMS désactivées (variables TWILIO_* manquantes)")
        return False

    try:
        numero_e164 = format_numero_e164(numero_destinataire)
        _client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=numero_e164
        )
        print(f"✅ SMS envoyé à {numero_e164}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi SMS: {e}")
        return False


def notifier_transaction_sms(numero_expediteur: str, numero_destinataire: str,
                              type_operation: str, montant: float, frais: float,
                              status: str, transaction_id: str):
    """Envoie un SMS de notification aux deux parties d'une transaction"""

    emoji = {"TRANSFERT": "📤", "RETRAIT": "💳", "DEPOT": "💰"}.get(type_operation, "💸")
    date_str = datetime.now().strftime('%d/%m %H:%M')
    ref = transaction_id[:8]

    if numero_expediteur and numero_expediteur != "DEPOT_SYSTEM":
        msg_exp = (
            f"{emoji} TRANSFER: {type_operation} de {montant:,.0f} XAF envoyé "
            f"(frais {frais:,.0f} XAF). Réf: {ref}. {date_str}"
        )
        envoyer_sms(numero_expediteur, msg_exp)

    if numero_destinataire:
        msg_dest = (
            f"{emoji} TRANSFER: {type_operation} de {montant:,.0f} XAF reçu. "
            f"Réf: {ref}. {date_str}"
        )
        envoyer_sms(numero_destinataire, msg_dest)
