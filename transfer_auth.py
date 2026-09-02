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
