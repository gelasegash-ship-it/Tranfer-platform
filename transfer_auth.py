"""
TRANSFER PLATFORM - Authentification
PIN hashé (bcrypt) + tokens JWT + rôle administrateur
"""

import os
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext

JWT_SECRET = os.getenv('JWT_SECRET', 'change-moi-en-production-clé-longue-aléatoire')
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_pin(pin: str) -> str:
    """Hash un PIN (jamais stocké en clair)"""
    return pwd_context.hash(pin)


def verifier_pin(pin: str, pin_hash: str) -> bool:
    """Vérifie un PIN contre son hash"""
    if not pin_hash:
        return False
    try:
        return pwd_context.verify(pin, pin_hash)
    except Exception:
        return False


def creer_token(numero_mtn: str, is_admin: bool = False) -> str:
    """Crée un token JWT de session"""
    payload = {
        "sub": numero_mtn,
        "is_admin": is_admin,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decoder_token(token: str) -> dict:
    """Décode et valide un token JWT. Lève une exception si invalide/expiré."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
