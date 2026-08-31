"""
TRANSFER PLATFORM - FastAPI Backend
API REST pour gérer transferts, retraits, comptes
Intégration PayPal, Stripe, MTN, etc.
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
from datetime import datetime
import hashlib
import hmac
from transfer_backend_sqlite import TransfertManager, TypeOperation

# ============================================================================
# CONFIGURATION
# ============================================================================

app = FastAPI(
    title="TRANSFER Platform API",
    version="3.0.0",
    description="API de gestion des transferts d'argent africains"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Manager de transferts
manager = TransfertManager(db_path=os.getenv('DB_PATH', 'gestion_transfert.db'))

# Clés API (à charger depuis .env)
PAYPAL_SECRET = os.getenv('PAYPAL_SECRET', '')
STRIPE_SECRET = os.getenv('STRIPE_SECRET', '')
MTN_API_KEY = os.getenv('MTN_API_KEY', '')
API_KEY = os.getenv('API_KEY', 'transfer-secret-key-2026')

# ============================================================================
# MODELS PYDANTIC
# ============================================================================

class CompteCreate(BaseModel):
    numero_mtn: str
    nom: str
    type_compte: str  # AGENT, CLIENT, BENEFICIAIRE
    solde_initial: float = 0
    email: Optional[str] = None

class Compte(BaseModel):
    numero_mtn: str
    nom: str
    type_compte: str
    solde: float
    kyc_level: int
    status: str

class TransfertRequest(BaseModel):
    numero_mtn_agent: str
    numero_mtn_client: str
    montant: float
    frais: Optional[float] = None

class RetraitRequest(BaseModel):
    numero_mtn_client: str
    numero_mtn_agent: str
    montant: float
    frais: Optional[float] = None

class DepotRequest(BaseModel):
    numero_mtn_client: str
    montant: float

class TransfertResponse(BaseModel):
    success: bool
    transfer_id: str
    message: str
    details: Optional[dict] = None

# ============================================================================
# AUTHENTICATION
# ============================================================================

async def verify_api_key(request: Request):
    """Vérifie la clé API"""
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key invalide")
    return api_key

# ============================================================================
# ENDPOINTS - COMPTES
# ============================================================================

@app.post("/api/comptes", tags=["Comptes"])
async def creer_compte(compte: CompteCreate, api_key = Depends(verify_api_key)):
    """Crée un nouveau compte"""
    try:
        success = manager.creer_compte(
            numero_mtn=compte.numero_mtn,
            nom=compte.nom,
            type_compte=compte.type_compte,
            solde_initial=compte.solde_initial,
            email=compte.email
        )
        
        if success:
            return {
                "success": True,
                "message": f"Compte créé: {compte.numero_mtn}",
                "numero_mtn": compte.numero_mtn
            }
        else:
            raise HTTPException(status_code=400, detail="Compte déjà existant")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/comptes/{numero_mtn}", tags=["Comptes"])
async def obtenir_compte(numero_mtn: str):
    """Récupère les détails d'un compte"""
    compte = manager.obtenir_compte(numero_mtn)
    
    if not compte:
        raise HTTPException(status_code=404, detail="Compte non trouvé")
    
    return compte

@app.get("/api/comptes", tags=["Comptes"])
async def lister_comptes(type_compte: Optional[str] = None):
    """Liste tous les comptes"""
    comptes = manager.lister_comptes(type_compte)
    return {"total": len(comptes), "comptes": comptes}

@app.get("/api/comptes/{numero_mtn}/solde", tags=["Comptes"])
async def obtenir_solde(numero_mtn: str):
    """Récupère le solde d'un compte"""
    solde = manager.obtenir_solde(numero_mtn)
    
    if solde == 0 and not manager.obtenir_compte(numero_mtn):
        raise HTTPException(status_code=404, detail="Compte non trouvé")
    
    return {
        "numero_mtn": numero_mtn,
        "solde": solde,
        "devise": "XAF"
    }

@app.get("/api/comptes/{numero_mtn}/statistiques", tags=["Comptes"])
async def obtenir_statistiques(numero_mtn: str):
    """Obtient les statistiques d'un compte"""
    stats = manager.obtenir_statistiques(numero_mtn)
    
    if not stats:
        raise HTTPException(status_code=404, detail="Compte non trouvé")
    
    return stats

# ============================================================================
# ENDPOINTS - TRANSFERTS
# ============================================================================

@app.post("/api/transferts", tags=["Transferts"])
async def creer_transfert(req: TransfertRequest, api_key = Depends(verify_api_key)):
    """Crée un transfert du agent vers client"""
    success, result = manager.effectuer_transfert(
        numero_mtn_agent=req.numero_mtn_agent,
        numero_mtn_client=req.numero_mtn_client,
        montant=req.montant,
        frais=req.frais
    )
    
    if success:
        transfert = manager.obtenir_transfert(result)
        return {
            "success": True,
            "transfer_id": result,
            "message": "Transfert réussi",
            "details": {
                "montant": transfert['montant'],
                "frais": transfert['frais'],
                "status": transfert['status'],
                "date": transfert['date_creation']
            }
        }
    else:
        raise HTTPException(status_code=400, detail=result)

@app.get("/api/transferts/{transfer_id}", tags=["Transferts"])
async def obtenir_transfert(transfer_id: str):
    """Récupère les détails d'un transfert"""
    transfert = manager.obtenir_transfert(transfer_id)
    
    if not transfert:
        raise HTTPException(status_code=404, detail="Transfert non trouvé")
    
    return transfert

# ============================================================================
# ENDPOINTS - RETRAITS
# ============================================================================

@app.post("/api/retraits", tags=["Retraits"])
async def creer_retrait(req: RetraitRequest, api_key = Depends(verify_api_key)):
    """Crée un retrait du client vers agent"""
    success, result = manager.effectuer_retrait(
        numero_mtn_client=req.numero_mtn_client,
        numero_mtn_agent=req.numero_mtn_agent,
        montant=req.montant,
        frais=req.frais
    )
    
    if success:
        retrait = manager.obtenir_transfert(result)
        return {
            "success": True,
            "retrait_id": result,
            "message": "Retrait réussi",
            "details": {
                "montant": retrait['montant'],
                "frais": retrait['frais'],
                "status": retrait['status']
            }
        }
    else:
        raise HTTPException(status_code=400, detail=result)

# ============================================================================
# ENDPOINTS - DÉPÔTS
# ============================================================================

@app.post("/api/depots", tags=["Dépôts"])
async def creer_depot(req: DepotRequest, api_key = Depends(verify_api_key)):
    """Crée un dépôt vers un compte client"""
    success, result = manager.effectuer_depot(
        numero_mtn_client=req.numero_mtn_client,
        montant=req.montant
    )
    
    if success:
        depot = manager.obtenir_transfert(result)
        return {
            "success": True,
            "depot_id": result,
            "message": "Dépôt effectué",
            "details": {
                "montant": depot['montant'],
                "status": depot['status']
            }
        }
    else:
        raise HTTPException(status_code=400, detail=result)

# ============================================================================
# ENDPOINTS - HISTORIQUE
# ============================================================================

@app.get("/api/historique/{numero_mtn}", tags=["Historique"])
async def obtenir_historique(numero_mtn: str, limit: int = 50):
    """Récupère l'historique d'un compte"""
    historique = manager.obtenir_historique(numero_mtn, limit)
    return {
        "numero_mtn": numero_mtn,
        "total": len(historique),
        "historique": historique
    }

# ============================================================================
# ENDPOINTS - INTÉGRATION PAYPAL (Webhook)
# ============================================================================

@app.post("/webhooks/paypal", tags=["Webhooks"])
async def webhook_paypal(request: Request):
    """Webhook PayPal pour les paiements (avec vérification de signature réelle)"""
    body = await request.body()
    headers = dict(request.headers)

    from transfer_paypal import verifier_signature_webhook, PAYPAL_ENABLED

    if not PAYPAL_ENABLED:
        raise HTTPException(status_code=503, detail="PayPal non configuré sur ce serveur")

    if not verifier_signature_webhook(headers, body):
        raise HTTPException(status_code=401, detail="Signature webhook invalide")

    data = json.loads(body)
    event_type = data.get('event_type')

    if event_type == 'PAYMENT.CAPTURE.COMPLETED' or event_type == 'CHECKOUT.ORDER.APPROVED':
        resource = data.get('resource', {})
        purchase_units = resource.get('purchase_units', [{}])
        numero_mtn = purchase_units[0].get('custom_id') if purchase_units else None
        montant = float(resource.get('amount', {}).get('value', 0))

        if numero_mtn and montant > 0:
            success, result = manager.effectuer_depot(numero_mtn, montant)
            return {"success": success, "deposit_id": result}

    return {"success": True, "message": "Webhook reçu"}


@app.post("/api/paypal/creer-paiement", tags=["PayPal"])
async def creer_paiement_paypal_endpoint(numero_mtn: str, montant: float,
                                          devise: str = "USD",
                                          api_key = Depends(verify_api_key)):
    """Crée un lien de paiement PayPal pour recharger un compte TRANSFER"""
    from transfer_paypal import creer_paiement_paypal, PAYPAL_ENABLED

    if not PAYPAL_ENABLED:
        raise HTTPException(status_code=503, detail="PayPal non configuré sur ce serveur")

    try:
        resultat = creer_paiement_paypal(montant, devise, numero_mtn)
        return resultat
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ENDPOINTS - INTÉGRATION STRIPE (Webhook)
# ============================================================================

@app.post("/webhooks/stripe", tags=["Webhooks"])
async def webhook_stripe(request: Request):
    """Webhook Stripe pour les paiements"""
    body = await request.body()
    
    data = json.loads(body)
    event_type = data.get('type')
    
    if event_type == 'charge.succeeded':
        # Créer un dépôt
        charge = data.get('data', {}).get('object', {})
        numero_mtn = charge.get('metadata', {}).get('numero_mtn')
        montant = charge.get('amount') / 100  # Stripe en cents
        
        if numero_mtn:
            success, result = manager.effectuer_depot(numero_mtn, montant)
            return {"success": success}
    
    return {"success": True}

# ============================================================================
# ENDPOINTS - SANTÉ
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Vérification de santé de l'API"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "database": "connected"
    }

@app.get("/api/stats", tags=["Stats"])
async def global_stats():
    """Statistiques globales"""
    comptes = manager.lister_comptes()
    solde_total = sum(c['solde'] for c in comptes)
    
    return {
        "total_comptes": len(comptes),
        "solde_total_plateforme": solde_total,
        "agents": len([c for c in comptes if c['type_compte'] == 'AGENT']),
        "clients": len([c for c in comptes if c['type_compte'] == 'CLIENT']),
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "message": exc.detail,
            "timestamp": datetime.now().isoformat()
        },
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "message": "Erreur interne du serveur",
            "timestamp": datetime.now().isoformat()
        },
    )

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"🚀 API TRANSFER Platform démarrée sur {host}:{port}")
    uvicorn.run(app, host=host, port=port)
