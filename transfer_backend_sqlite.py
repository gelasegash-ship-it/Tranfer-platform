#!/usr/bin/env python3
"""
TRANSFER PLATFORM - Backend avec support PostgreSQL persistant
Utilise DATABASE_URL (PostgreSQL) si disponible, sinon SQLite en local.
"""

import os
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
else:
    import sqlite3

# ============================================================================
# TYPES & ENUMS
# ============================================================================

class TypeCompte(Enum):
    AGENT = "AGENT"
    CLIENT = "CLIENT"
    BENEFICIAIRE = "BENEFICIAIRE"

class TypeOperation(Enum):
    TRANSFERT = "TRANSFERT"
    RETRAIT = "RETRAIT"
    DEPOT = "DEPOT"
    REMBOURSEMENT = "REMBOURSEMENT"

class StatusTransfert(Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

@dataclass
class Compte:
    numero_mtn: str
    nom: str
    type_compte: str
    solde: float
    date_creation: str
    status: str = "ACTIF"
    kyc_level: int = 0

# ============================================================================
# ADAPTATEUR SQL (place-holders différents entre SQLite ? et Postgres %s)
# ============================================================================

def ph(n: int) -> str:
    """Retourne les placeholders adaptés au moteur (? pour SQLite, %s pour Postgres)"""
    mark = "%s" if USE_POSTGRES else "?"
    return ", ".join([mark] * n)

def p(single: bool = True) -> str:
    return "%s" if USE_POSTGRES else "?"

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class TransfertManager:
    """Gère tous les transferts et les comptes (PostgreSQL ou SQLite)"""

    def __init__(self, db_path: str = 'gestion_transfert.db'):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        if USE_POSTGRES:
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
            return conn
        else:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def _dict(self, row):
        if row is None:
            return None
        return dict(row)

    # ========================================================================
    # INITIALISATION
    # ========================================================================

    def init_database(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        serial_pk = "SERIAL" if USE_POSTGRES else "INTEGER"
        text_pk = "TEXT PRIMARY KEY"

        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS comptes (
                numero_mtn TEXT PRIMARY KEY,
                nom TEXT NOT NULL,
                type_compte TEXT NOT NULL,
                solde REAL NOT NULL DEFAULT 0,
                date_creation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIF',
                kyc_level INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transferts (
                id TEXT PRIMARY KEY,
                expediteur TEXT NOT NULL,
                destinataire TEXT NOT NULL,
                montant REAL NOT NULL,
                frais REAL NOT NULL DEFAULT 0,
                type_operation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                date_creation TEXT NOT NULL,
                date_completion TEXT,
                reference TEXT,
                preuve_blockchain TEXT,
                notes TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historique_detaille (
                id TEXT PRIMARY KEY,
                id_transfert TEXT NOT NULL,
                numero_mtn TEXT NOT NULL,
                action TEXT NOT NULL,
                montant_avant REAL,
                montant_apres REAL,
                date_action TEXT NOT NULL,
                details TEXT
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Base de données initialisée ({'PostgreSQL' if USE_POSTGRES else 'SQLite'})")

    # ========================================================================
    # COMPTES
    # ========================================================================

    def creer_compte(self, numero_mtn: str, nom: str, type_compte: str,
                      solde_initial: float = 0) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"INSERT INTO comptes (numero_mtn, nom, type_compte, solde, date_creation) "
                f"VALUES ({ph(5)})",
                (numero_mtn, nom, type_compte, solde_initial, datetime.now().isoformat())
            )
            conn.commit()
            print(f"✅ Compte créé: {numero_mtn} ({nom})")
            return True
        except Exception as e:
            conn.rollback()
            print(f"❌ Compte déjà existant ou erreur: {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    def obtenir_compte(self, numero_mtn: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM comptes WHERE numero_mtn = {p()}", (numero_mtn,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return self._dict(row)

    def obtenir_solde(self, numero_mtn: str) -> float:
        compte = self.obtenir_compte(numero_mtn)
        return compte['solde'] if compte else 0

    def lister_comptes(self, type_compte: Optional[str] = None) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        if type_compte:
            cursor.execute(
                f"SELECT * FROM comptes WHERE type_compte = {p()} ORDER BY date_creation DESC",
                (type_compte,)
            )
        else:
            cursor.execute("SELECT * FROM comptes ORDER BY date_creation DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [self._dict(r) for r in rows]

    # ========================================================================
    # TRANSFERTS / RETRAITS / DEPOTS
    # ========================================================================

    def effectuer_transfert(self, numero_mtn_agent: str, numero_mtn_client: str,
                             montant: float, frais: float = None) -> Tuple[bool, str]:
        return self._executer_operation(
            TypeOperation.TRANSFERT.value, numero_mtn_agent, numero_mtn_client, montant, frais
        )

    def effectuer_retrait(self, numero_mtn_client: str, numero_mtn_agent: str,
                           montant: float, frais: float = None) -> Tuple[bool, str]:
        return self._executer_operation(
            TypeOperation.RETRAIT.value, numero_mtn_client, numero_mtn_agent, montant, frais
        )

    def effectuer_depot(self, numero_mtn_client: str, montant: float) -> Tuple[bool, str]:
        return self._executer_operation(
            TypeOperation.DEPOT.value, "DEPOT_SYSTEM", numero_mtn_client, montant, 0
        )

    def _executer_operation(self, type_operation: str, expediteur: str,
                             destinataire: str, montant: float,
                             frais: float = None) -> Tuple[bool, str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if frais is None:
                frais = round(montant * 0.005, 2)
            montant_total = montant + frais

            if expediteur != "DEPOT_SYSTEM":
                cursor.execute(f"SELECT * FROM comptes WHERE numero_mtn = {p()}", (expediteur,))
                compte_exp = self._dict(cursor.fetchone())
                if not compte_exp:
                    return False, f"Compte expéditeur inexistant: {expediteur}"
                if compte_exp['solde'] < montant_total:
                    return False, f"Solde insuffisant: {compte_exp['solde']} < {montant_total}"

            cursor.execute(f"SELECT * FROM comptes WHERE numero_mtn = {p()}", (destinataire,))
            compte_dest = self._dict(cursor.fetchone())
            if not compte_dest:
                return False, f"Compte destinataire inexistant: {destinataire}"

            transfer_id = str(uuid.uuid4())
            date_now = datetime.now().isoformat()

            cursor.execute(
                f"INSERT INTO transferts (id, expediteur, destinataire, montant, frais, "
                f"type_operation, status, date_creation) VALUES ({ph(8)})",
                (transfer_id, expediteur, destinataire, montant, frais,
                 type_operation, StatusTransfert.PROCESSING.value, date_now)
            )

            if expediteur != "DEPOT_SYSTEM":
                nouveau_solde_exp = compte_exp['solde'] - montant_total
                cursor.execute(
                    f"UPDATE comptes SET solde = {p()} WHERE numero_mtn = {p()}",
                    (nouveau_solde_exp, expediteur)
                )

            nouveau_solde_dest = compte_dest['solde'] + montant
            cursor.execute(
                f"UPDATE comptes SET solde = {p()} WHERE numero_mtn = {p()}",
                (nouveau_solde_dest, destinataire)
            )

            cursor.execute(
                f"UPDATE transferts SET status = {p()}, date_completion = {p()} WHERE id = {p()}",
                (StatusTransfert.COMPLETED.value, date_now, transfer_id)
            )

            conn.commit()
            return True, transfer_id

        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    def obtenir_transfert(self, transfer_id: str) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM transferts WHERE id = {p()}", (transfer_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return self._dict(row)

    def obtenir_historique(self, numero_mtn: str, limit: int = 50) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM transferts WHERE expediteur = {p()} OR destinataire = {p()} "
            f"ORDER BY date_creation DESC LIMIT {p()}",
            (numero_mtn, numero_mtn, limit)
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [self._dict(r) for r in rows]

    def obtenir_statistiques(self, numero_mtn: str) -> Dict:
        compte = self.obtenir_compte(numero_mtn)
        if not compte:
            return {}
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT COUNT(*) as total FROM transferts WHERE expediteur = {p()}", (numero_mtn,))
        nb_envoyes = self._dict(cursor.fetchone())['total']

        cursor.execute(f"SELECT COUNT(*) as total FROM transferts WHERE destinataire = {p()}", (numero_mtn,))
        nb_recus = self._dict(cursor.fetchone())['total']

        cursor.close()
        conn.close()

        return {
            'solde_actuel': compte['solde'],
            'transferts_envoyes': nb_envoyes,
            'transferts_recus': nb_recus,
            'kyc_level': compte.get('kyc_level', 0),
            'status': compte.get('status', 'ACTIF')
        }
