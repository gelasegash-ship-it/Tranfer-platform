#!/usr/bin/env python3
"""
TRANSFER PLATFORM - Backend SQLite/Transaction Management
Gestion complète des transferts, retraits, et comptes
Compatible avec MTN, agents, et clients
"""

import sqlite3
import json
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

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
    limite_quotidienne: float = 5000000.0
    limite_mensuelle: float = 50000000.0

@dataclass
class Transfert:
    id: str
    expediteur: str
    destinataire: str
    montant: float
    frais: float
    type_operation: str
    status: str
    date_creation: str
    date_completion: Optional[str] = None
    reference: str = ""
    preuve_blockchain: Optional[str] = None

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class TransfertManager:
    """Gère tous les transferts et les comptes"""
    
    def __init__(self, db_path: str = 'gestion_transfert.db'):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Obtient une connexion à la base de données"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========================================================================
    # INITIALISATION DE LA BASE DE DONNÉES
    # ========================================================================
    
    def init_database(self):
        """Crée les tables si elles n'existent pas"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table des comptes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comptes (
                numero_mtn TEXT PRIMARY KEY,
                nom TEXT NOT NULL,
                type_compte TEXT NOT NULL,
                solde REAL NOT NULL DEFAULT 0,
                date_creation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIF',
                kyc_level INTEGER DEFAULT 0,
                limite_quotidienne REAL DEFAULT 5000000,
                limite_mensuelle REAL DEFAULT 50000000,
                solde_utilise_jour REAL DEFAULT 0,
                solde_utilise_mois REAL DEFAULT 0
            )
        """)
        
        # Table des transferts
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
                notes TEXT,
                FOREIGN KEY (expediteur) REFERENCES comptes(numero_mtn),
                FOREIGN KEY (destinataire) REFERENCES comptes(numero_mtn)
            )
        """)
        
        # Table d'historique détaillé
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historique_detaille (
                id TEXT PRIMARY KEY,
                id_transfert TEXT NOT NULL,
                numero_mtn TEXT NOT NULL,
                action TEXT NOT NULL,
                montant_avant REAL,
                montant_apres REAL,
                date_action TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (id_transfert) REFERENCES transferts(id),
                FOREIGN KEY (numero_mtn) REFERENCES comptes(numero_mtn)
            )
        """)
        
        # Table des limites quotidiennes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS limites_quotidiennes (
                numero_mtn TEXT PRIMARY KEY,
                date DATE NOT NULL,
                montant_utilise REAL DEFAULT 0,
                FOREIGN KEY (numero_mtn) REFERENCES comptes(numero_mtn)
            )
        """)
        
        # Créer les index pour performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transfert_expediteur 
            ON transferts(expediteur)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transfert_destinataire 
            ON transferts(destinataire)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transfert_date 
            ON transferts(date_creation)
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ Base de données initialisée")
    
    # ========================================================================
    # GESTION DES COMPTES
    # ========================================================================
    
    def creer_compte(self, numero_mtn: str, nom: str, type_compte: str, 
                    solde_initial: float = 0) -> bool:
        """Crée un nouveau compte"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO comptes 
                (numero_mtn, nom, type_compte, solde, date_creation)
                VALUES (?, ?, ?, ?, ?)
            """, (numero_mtn, nom, type_compte, solde_initial, datetime.now().isoformat()))
            
            conn.commit()
            print(f"✅ Compte créé: {numero_mtn} ({nom})")
            return True
            
        except sqlite3.IntegrityError:
            print(f"❌ Compte déjà existant: {numero_mtn}")
            return False
        finally:
            conn.close()
    
    def obtenir_compte(self, numero_mtn: str) -> Optional[Dict]:
        """Récupère un compte par numéro MTN"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM comptes WHERE numero_mtn = ?", (numero_mtn,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def obtenir_solde(self, numero_mtn: str) -> float:
        """Récupère le solde d'un compte"""
        compte = self.obtenir_compte(numero_mtn)
        return compte['solde'] if compte else 0
    
    def mettre_a_jour_solde(self, numero_mtn: str, nouveau_solde: float) -> bool:
        """Met à jour le solde d'un compte"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "UPDATE comptes SET solde = ? WHERE numero_mtn = ?",
                (nouveau_solde, numero_mtn)
            )
            conn.commit()
            return True
        finally:
            conn.close()
    
    def lister_comptes(self, type_compte: Optional[str] = None) -> List[Dict]:
        """Liste tous les comptes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if type_compte:
            cursor.execute(
                "SELECT * FROM comptes WHERE type_compte = ? ORDER BY date_creation DESC",
                (type_compte,)
            )
        else:
            cursor.execute("SELECT * FROM comptes ORDER BY date_creation DESC")
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ========================================================================
    # GESTION DES TRANSFERTS
    # ========================================================================
    
    def effectuer_transfert(self, numero_mtn_agent: str, numero_mtn_client: str, 
                           montant: float, frais: float = None) -> Tuple[bool, str]:
        """Effectue un transfert du agent au client"""
        return self._executer_operation(
            type_operation=TypeOperation.TRANSFERT.value,
            expediteur=numero_mtn_agent,
            destinataire=numero_mtn_client,
            montant=montant,
            frais=frais
        )
    
    def effectuer_retrait(self, numero_mtn_client: str, numero_mtn_agent: str,
                         montant: float, frais: float = None) -> Tuple[bool, str]:
        """Effectue un retrait du client à l'agent"""
        return self._executer_operation(
            type_operation=TypeOperation.RETRAIT.value,
            expediteur=numero_mtn_client,
            destinataire=numero_mtn_agent,
            montant=montant,
            frais=frais
        )
    
    def effectuer_depot(self, numero_mtn_client: str, montant: float) -> Tuple[bool, str]:
        """Effectue un dépôt vers un compte client"""
        return self._executer_operation(
            type_operation=TypeOperation.DEPOT.value,
            expediteur="DEPOT_SYSTEM",
            destinataire=numero_mtn_client,
            montant=montant,
            frais=0
        )
    
    def _executer_operation(self, type_operation: str, expediteur: str, 
                           destinataire: str, montant: float, 
                           frais: float = None) -> Tuple[bool, str]:
        """Exécute une opération de transfert avec vérifications"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Calcul des frais (0.5% par défaut)
            if frais is None:
                frais = montant * 0.005
            
            montant_total = montant + frais
            
            # Vérifications préalables
            if expediteur != "DEPOSIT_SYSTEM":
                compte_exp = self.obtenir_compte(expediteur)
                if not compte_exp:
                    return False, f"Compte expéditeur inexistant: {expediteur}"
                
                if compte_exp['solde'] < montant_total:
                    return False, f"Solde insuffisant: {compte_exp['solde']} < {montant_total}"
            
            compte_dest = self.obtenir_compte(destinataire)
            if not compte_dest:
                return False, f"Compte destinataire inexistant: {destinataire}"
            
            # Génération de l'ID de transfert
            transfer_id = str(uuid.uuid4())
            date_now = datetime.now().isoformat()
            
            # Insertion du transfert
            cursor.execute("""
                INSERT INTO transferts 
                (id, expediteur, destinataire, montant, frais, type_operation, 
                 status, date_creation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (transfer_id, expediteur, destinataire, montant, frais, 
                  type_operation, StatusTransfert.PROCESSING.value, date_now))
            
            # Mise à jour des soldes
            if expediteur != "DEPOSIT_SYSTEM":
                solde_exp = compte_exp['solde'] - montant_total
                cursor.execute(
                    "UPDATE comptes SET solde = ? WHERE numero_mtn = ?",
                    (solde_exp, expediteur)
                )
            
            solde_dest = compte_dest['solde'] + montant
            cursor.execute(
                "UPDATE comptes SET solde = ? WHERE numero_mtn = ?",
                (solde_dest, destinataire)
            )
            
            # Enregistrement dans l'historique détaillé
            hist_id_exp = str(uuid.uuid4()) if expediteur != "DEPOSIT_SYSTEM" else None
            hist_id_dest = str(uuid.uuid4())
            
            if expediteur != "DEPOSIT_SYSTEM":
                cursor.execute("""
                    INSERT INTO historique_detaille
                    (id, id_transfert, numero_mtn, action, montant_avant, 
                     montant_apres, date_action, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (hist_id_exp, transfer_id, expediteur, "DEBIT", 
                      compte_exp['solde'], solde_exp, date_now, 
                      f"{type_operation} vers {destinataire}"))
            
            cursor.execute("""
                INSERT INTO historique_detaille
                (id, id_transfert, numero_mtn, action, montant_avant, 
                 montant_apres, date_action, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (hist_id_dest, transfer_id, destinataire, "CREDIT", 
                  compte_dest['solde'], solde_dest, date_now, 
                  f"{type_operation} de {expediteur}"))
            
            # Marquer comme complété
            cursor.execute(
                "UPDATE transferts SET status = ?, date_completion = ? WHERE id = ?",
                (StatusTransfert.COMPLETED.value, date_now, transfer_id)
            )
            
            conn.commit()
            return True, transfer_id
            
        except sqlite3.Error as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()
    
    def obtenir_transfert(self, transfer_id: str) -> Optional[Dict]:
        """Récupère les détails d'un transfert"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM transferts WHERE id = ?", (transfer_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def obtenir_historique(self, numero_mtn: str, limit: int = 50) -> List[Dict]:
        """Récupère l'historique des transferts d'un compte"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM transferts 
            WHERE expediteur = ? OR destinataire = ?
            ORDER BY date_creation DESC
            LIMIT ?
        """, (numero_mtn, numero_mtn, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def obtenir_statistiques(self, numero_mtn: str) -> Dict:
        """Obtient les statistiques d'un compte"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        compte = self.obtenir_compte(numero_mtn)
        if not compte:
            return {}
        
        # Nombre de transferts effectués
        cursor.execute(
            "SELECT COUNT(*) as total FROM transferts WHERE expediteur = ?",
            (numero_mtn,)
        )
        nb_envoyes = cursor.fetchone()['total']
        
        # Nombre de transferts reçus
        cursor.execute(
            "SELECT COUNT(*) as total FROM transferts WHERE destinataire = ?",
            (numero_mtn,)
        )
        nb_recus = cursor.fetchone()['total']
        
        # Montant total envoyé
        cursor.execute(
            "SELECT SUM(montant) as total FROM transferts WHERE expediteur = ? AND status = ?",
            (numero_mtn, StatusTransfert.COMPLETED.value)
        )
        montant_envoye = cursor.fetchone()['total'] or 0
        
        # Montant total reçu
        cursor.execute(
            "SELECT SUM(montant) as total FROM transferts WHERE destinataire = ? AND status = ?",
            (numero_mtn, StatusTransfert.COMPLETED.value)
        )
        montant_recu = cursor.fetchone()['total'] or 0
        
        conn.close()
        
        return {
            'solde_actuel': compte['solde'],
            'transferts_envoyes': nb_envoyes,
            'transferts_recus': nb_recus,
            'montant_total_envoye': montant_envoye,
            'montant_total_recu': montant_recu,
            'kyc_level': compte['kyc_level'],
            'status': compte['status']
        }

# ============================================================================
# EXEMPLE D'UTILISATION
# ============================================================================

def exemple_utilisation():
    """Démonstration du système"""
    
    # Initialiser le manager
    manager = TransfertManager()
    
    print("\n" + "="*60)
    print("TRANSFER PLATFORM - Gestion des Transferts")
    print("="*60 + "\n")
    
    # Créer des comptes
    print("📝 Création des comptes...")
    manager.creer_compte('068078227', 'Agent Gelase', 'AGENT', 100000)
    manager.creer_compte('243777000000', 'Client Jean', 'CLIENT', 50000)
    manager.creer_compte('243777111111', 'Client Marie', 'CLIENT', 30000)
    
    print("\n💰 Soldes initiaux:")
    for compte in manager.lister_comptes():
        print(f"  {compte['nom']:20} | Solde: {compte['solde']:>10.0f} XAF")
    
    # Effectuer un transfert
    print("\n📤 Effectuer un transfert...")
    success, transfer_id = manager.effectuer_transfert(
        numero_mtn_agent='068078227',
        numero_mtn_client='243777000000',
        montant=10000
    )
    
    if success:
        print(f"✅ Transfert réussi! ID: {transfer_id}")
        transfert = manager.obtenir_transfert(transfer_id)
        print(f"  Montant: {transfert['montant']} XAF")
        print(f"  Frais: {transfert['frais']} XAF")
        print(f"  Status: {transfert['status']}")
    else:
        print(f"❌ Erreur: {transfer_id}")
    
    # Effectuer un retrait
    print("\n💳 Effectuer un retrait...")
    success, retrait_id = manager.effectuer_retrait(
        numero_mtn_client='243777000000',
        numero_mtn_agent='068078227',
        montant=5000
    )
    
    if success:
        print(f"✅ Retrait réussi! ID: {retrait_id}")
    
    print("\n💰 Soldes après transactions:")
    for compte in manager.lister_comptes():
        stats = manager.obtenir_statistiques(compte['numero_mtn'])
        print(f"  {compte['nom']:20} | Solde: {stats['solde_actuel']:>10.0f} XAF")
    
    print("\n📊 Historique (Client Jean):")
    for txn in manager.obtenir_historique('243777000000', limit=10):
        print(f"  {txn['date_creation']} | {txn['type_operation']:10} | "
              f"{txn['montant']:>8.0f} XAF | {txn['status']}")
    
    print("\n" + "="*60)

if __name__ == "__main__":
    exemple_utilisation()
