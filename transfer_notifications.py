"""
TRANSFER PLATFORM - Notifications Email
Envoie un email de confirmation à chaque transaction (transfert, retrait, dépôt)
Utilise Gmail SMTP (gratuit, via mot de passe d'application)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD', '')
NOTIFICATIONS_ENABLED = bool(GMAIL_ADDRESS and GMAIL_APP_PASSWORD)

# ============================================================================
# TEMPLATES D'EMAIL
# ============================================================================

def template_transaction(type_operation: str, montant: float, frais: float,
                          expediteur: str, destinataire: str, status: str,
                          transaction_id: str) -> str:
    """Génère le contenu HTML de l'email de notification"""

    emoji = {"TRANSFERT": "📤", "RETRAIT": "💳", "DEPOT": "💰"}.get(type_operation, "💸")
    couleur = "#22c55e" if status == "COMPLETED" else "#facc15"

    return f"""
    <html>
    <body style="font-family: -apple-system, sans-serif; background: #0f172a; padding: 20px; color: white;">
        <div style="max-width: 480px; margin: 0 auto; background: rgba(255,255,255,0.08);
                    border-radius: 16px; padding: 24px; border: 1px solid rgba(59,130,246,0.3);">
            <h1 style="text-align:center; margin-bottom: 4px;">💸 TRANSFER</h1>
            <p style="text-align:center; color:#93c5fd; font-size:0.85rem; margin-bottom:24px;">
                Money moves fast • We move faster
            </p>

            <div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 20px; text-align: center;">
                <div style="font-size: 2.5rem;">{emoji}</div>
                <div style="font-size: 1.2rem; font-weight: bold; margin: 8px 0;">
                    {type_operation}
                </div>
                <div style="font-size: 2rem; font-weight: bold; color: {couleur};">
                    {montant:,.0f} XAF
                </div>
                <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 4px;">
                    Frais: {frais:,.0f} XAF
                </div>
            </div>

            <table style="width: 100%; margin-top: 20px; font-size: 0.85rem; color: #cbd5e1;">
                <tr><td style="padding: 6px 0;">De</td><td style="text-align:right;">{expediteur}</td></tr>
                <tr><td style="padding: 6px 0;">Vers</td><td style="text-align:right;">{destinataire}</td></tr>
                <tr><td style="padding: 6px 0;">Statut</td><td style="text-align:right; color:{couleur};">{status}</td></tr>
                <tr><td style="padding: 6px 0;">Référence</td><td style="text-align:right; font-family: monospace; font-size:0.75rem;">{transaction_id[:8]}</td></tr>
                <tr><td style="padding: 6px 0;">Date</td><td style="text-align:right;">{datetime.now().strftime('%d/%m/%Y %H:%M')}</td></tr>
            </table>

            <p style="text-align:center; color:#64748b; font-size:0.75rem; margin-top: 24px;">
                Si vous n'êtes pas à l'origine de cette opération, contactez immédiatement le support.
            </p>
        </div>
    </body>
    </html>
    """

# ============================================================================
# ENVOI D'EMAIL
# ============================================================================

def envoyer_email(destinataire_email: str, sujet: str, contenu_html: str) -> bool:
    """Envoie un email via Gmail SMTP"""
    if not NOTIFICATIONS_ENABLED:
        print("⚠️ Notifications email désactivées (GMAIL_ADDRESS / GMAIL_APP_PASSWORD manquants)")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = sujet
        msg['From'] = f"TRANSFER Platform <{GMAIL_ADDRESS}>"
        msg['To'] = destinataire_email

        msg.attach(MIMEText(contenu_html, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)

        print(f"✅ Email envoyé à {destinataire_email}")
        return True

    except Exception as e:
        print(f"❌ Erreur envoi email: {e}")
        return False

def notifier_transaction(email_expediteur: str, email_destinataire: str,
                          type_operation: str, montant: float, frais: float,
                          expediteur: str, destinataire: str, status: str,
                          transaction_id: str):
    """Envoie une notification email pour une transaction (aux deux parties si emails fournis)"""

    contenu = template_transaction(
        type_operation, montant, frais, expediteur, destinataire, status, transaction_id
    )

    sujet_exp = f"💸 {type_operation} envoyé - {montant:,.0f} XAF"
    sujet_dest = f"💸 {type_operation} reçu - {montant:,.0f} XAF"

    if email_expediteur:
        envoyer_email(email_expediteur, sujet_exp, contenu)

    if email_destinataire:
        envoyer_email(email_destinataire, sujet_dest, contenu)
