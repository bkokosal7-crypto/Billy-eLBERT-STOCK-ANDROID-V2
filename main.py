import sys
import os
import json
import hmac
import hashlib
import shutil
import tempfile
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta

from PySide6.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QDialog,
    QLabel, QPushButton, QLineEdit, QTabWidget, QTableWidget,
    QSpinBox, QTableWidgetItem, QHeaderView, QMessageBox, QInputDialog,
    QDateEdit, QComboBox, QDoubleSpinBox, QAbstractItemView, QGraphicsDropShadowEffect, QScrollArea, QSizePolicy, QFrame, QGroupBox,
)
from PySide6.QtCore import Qt, QTimer, QDate, QStandardPaths, QUrl
from PySide6.QtWidgets import QGraphicsDropShadowEffect
from PySide6.QtGui import QPainter, QFont, QPen, QBrush, QIcon, QAction, QKeySequence, QDesktopServices, QColor

# ============================================================
# RESSOURCES / LOGO
# ============================================================
# Le logo reste dans le dossier du projet :
# Stock\Ressources\Billy.PNG
# Avec PyInstaller, les ressources sont recherchées aussi dans
# le dossier temporaire interne de l'EXE (_MEIPASS).
BASE_CODE = Path(__file__).resolve().parent
RESSOURCES = BASE_CODE / "Ressources"

if getattr(sys, "frozen", False):
    RESSOURCES_EXE = Path(getattr(sys, "_MEIPASS", BASE_CODE)) / "Ressources"
else:
    RESSOURCES_EXE = RESSOURCES

LOGO_CANDIDATS = [
    RESSOURCES_EXE / "Billy.PNG",
    RESSOURCES / "Billy.PNG",
    Path.cwd() / "Ressources" / "Billy.PNG",
]

LOGO_PATH = next((p for p in LOGO_CANDIDATS if p.exists()), RESSOURCES / "Billy.PNG")
# ============================================================
# CONFIGURATION
# ============================================================

# ============================================================
# COMPATIBILITÉ WINDOWS / ANDROID
# ============================================================
# Windows : le fonctionnement existant est conservé.
# Android : l'application sera générée en APK (et non en .exe).
# Les données doivent être placées dans le dossier privé et
# inscriptible de l'application Android.
ANDROID = sys.platform == "android"

# ============================================================
# DOSSIER CENTRAL DE DONNÉES DE L'APPLICATION
# ============================================================

if ANDROID:
    # Sur Android, les données restent dans l'espace privé de l'application
    _dossier_android = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    DOSSIER = Path(_dossier_android)
    DOSSIER.mkdir(parents=True, exist_ok=True)

else:
    # Sur Windows, toutes les données utilisateur sont centralisées
    # indépendamment de l'emplacement du fichier .exe.
    DOSSIER = Path(r"C:\Billy-eLBERT STOCK")
    DOSSIER.mkdir(parents=True, exist_ok=True)


# ============================================================
# SOUS-DOSSIERS PERMANENTS
# ============================================================

BROUILLONS_DIR = DOSSIER / "Brouillons"
BROUILLONS_DIR.mkdir(parents=True, exist_ok=True)
RAPPORTS_PDF_DIR = DOSSIER / "rapportPDF"
RAPPORTS_PDF_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVES_DIR = DOSSIER / "Archives"
MODE_FINAL_DIR = DOSSIER / "modefinal"
STOCK_DIR = DOSSIER / "stock"
STOCK_INITIAL_DIR = DOSSIER / "stockinitial"

ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
MODE_FINAL_DIR.mkdir(parents=True, exist_ok=True)
STOCK_DIR.mkdir(parents=True, exist_ok=True)
STOCK_INITIAL_DIR.mkdir(parents=True, exist_ok=True)

TAUX_USD_DEFAUT = 2250
MOT_DE_PASSE_ADMIN = "admin123"

# ============================================================
# MODE DÉVELOPPEUR — SOURCE EXTERNE ET VERSIONS
# ============================================================
# Cette zone est volontairement invisible dans le menu normal.
# Elle est ouverte uniquement avec Ctrl+Shift+Alt+B.
#
# Le code source utilisé pour les tests est conservé hors de l'EXE.
# Ainsi, le programme peut être modifié et testé sans reconstruire
# l'EXE à chaque changement. Une reconstruction reste nécessaire
# uniquement lorsque l'on veut publier une nouvelle version EXE.
DEV_ROOT = DOSSIER / "Developpeur"
DEV_SOURCE_DIR = DEV_ROOT / "Source"
DEV_BACKUPS_DIR = DEV_ROOT / "Sauvegardes_Code"
DEV_VERSIONS_DIR = DEV_ROOT / "Versions"

for _dossier_dev in (DEV_ROOT, DEV_SOURCE_DIR, DEV_BACKUPS_DIR, DEV_VERSIONS_DIR):
    _dossier_dev.mkdir(parents=True, exist_ok=True)

DEV_SOURCE_FILE = DEV_SOURCE_DIR / "main.py"


# ------------------------------------------------------------
# MODES DE FONCTIONNEMENT
# ------------------------------------------------------------
# Sans MODE_FINAL.flag : EXE de démonstration, réinitialisé à
# chaque lancement.
# Avec MODE_FINAL.flag : EXE final, données persistantes.
MODE_FINAL_FLAG = DOSSIER / "MODE_FINAL.flag"

# Sur Android, le flag et la base initiale peuvent être embarqués
# comme ressources en lecture seule. Le flag écrit dans DOSSIER reste
# prioritaire pour les données persistantes.
MODE_FINAL = (
    MODE_FINAL_FLAG.exists()
    or (RESSOURCES / "MODE_FINAL.flag").exists()
)

if ANDROID:
    INITIAL_DB = (
        DOSSIER / "stock_initial.db"
        if (DOSSIER / "stock_initial.db").exists()
        else RESSOURCES / "stock_initial.db"
    )
else:
    INITIAL_DB = DOSSIER / "stock_initial.db"

if MODE_FINAL:
    BASE = DOSSIER / "stock.db"
else:
    # Chaque lancement de la démo utilise une nouvelle base temporaire.
    # Sur Android, on utilise le dossier privé de l'application.
    if ANDROID:
        for ancien_demo in DOSSIER.glob("Billy-eLBERT-STOCK-demo-*.db"):
            try:
                ancien_demo.unlink()
            except Exception:
                pass
        BASE = DOSSIER / (
            "Billy-eLBERT-STOCK-demo-" + str(os.getpid()) + ".db"
        )
    else:
        # Fonctionnement Windows existant : base temporaire par lancement.
        for ancien_demo in Path(tempfile.gettempdir()).glob(
            "Billy-eLBERT-STOCK-demo-*.db"
        ):
            try:
                ancien_demo.unlink()
            except Exception:
                pass
        BASE = Path(tempfile.gettempdir()) / (
            "Billy-eLBERT-STOCK-demo-" + str(os.getpid()) + ".db"
        )

ARCHIVES_DIR = DOSSIER / "archives"
LICENSE_FILE = DOSSIER / "license.dat"
TRIAL_FILE = DOSSIER / "trial.dat"
TRIAL_DUREE_JOURS = 30
LICENSE_SECRET = "eLBERT-STOCK-2026-BILLY-FABRICE-KEY"

CLE_TRIAL_30 = "ELBERT-TRIAL30-EC4D4CDB7E2F"
CLE_VIE = "ELBERT-LIFETIME-72B7C6A9EE22"


# ============================================================
# BASE DE DONNÉES
# ============================================================

def preparer_base_finale():
    """Prépare la base persistante de l'EXE final à partir du modèle initial."""
    if not MODE_FINAL:
        return
    if not BASE.exists() and INITIAL_DB.exists():
        try:
            shutil.copy2(INITIAL_DB, BASE)
        except Exception:
            pass


preparer_base_finale()


def connexion():
    return sqlite3.connect(BASE)


def creer_base():
    conn = connexion()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produit TEXT NOT NULL,
            prix_fc REAL DEFAULT 0,
            stock REAL DEFAULT 0,
            date_expiration TEXT,
            visible INTEGER DEFAULT 1
        )
    """)

    cur.execute("PRAGMA table_info(produits)")
    colonnes = [ligne[1] for ligne in cur.fetchall()]

    if "prix_fc" not in colonnes:
        cur.execute("ALTER TABLE produits ADD COLUMN prix_fc REAL DEFAULT 0")
    if "stock" not in colonnes:
        cur.execute("ALTER TABLE produits ADD COLUMN stock REAL DEFAULT 0")
    if "date_expiration" not in colonnes:
        cur.execute("ALTER TABLE produits ADD COLUMN date_expiration TEXT")
    if "visible" not in colonnes:
        cur.execute("ALTER TABLE produits ADD COLUMN visible INTEGER DEFAULT 1")
    if "prix_achat_fc" not in colonnes:
        cur.execute("ALTER TABLE produits ADD COLUMN prix_achat_fc REAL DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parametres (
            cle TEXT PRIMARY KEY,
            valeur TEXT
        )
    """)

    cur.execute("SELECT valeur FROM parametres WHERE cle = 'taux_usd'")
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO parametres (cle, valeur) VALUES (?, ?)",
            ("taux_usd", str(TAUX_USD_DEFAUT))
        )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_vente TEXT NOT NULL UNIQUE,
            date TEXT NOT NULL,
            heure TEXT NOT NULL,
            nom_client TEXT DEFAULT '',
            total_fc REAL DEFAULT 0,
            total_usd REAL DEFAULT 0,
            statut TEXT DEFAULT 'VALIDEE'
        )
    """)

    cur.execute("PRAGMA table_info(ventes)")
    ventes_cols = [ligne[1] for ligne in cur.fetchall()]
    if "nom_client" not in ventes_cols:
        cur.execute("ALTER TABLE ventes ADD COLUMN nom_client TEXT DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vente_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vente_id INTEGER NOT NULL,
            produit_id INTEGER NOT NULL,
            produit TEXT NOT NULL,
            prix_fc REAL DEFAULT 0,
            quantite REAL DEFAULT 0,
            total_fc REAL DEFAULT 0,
            prix_achat_fc REAL DEFAULT 0,
            FOREIGN KEY (vente_id) REFERENCES ventes(id) ON DELETE CASCADE,
            FOREIGN KEY (produit_id) REFERENCES produits(id)
        )
    """)

    cur.execute("PRAGMA table_info(vente_details)")
    details_cols = [ligne[1] for ligne in cur.fetchall()]
    if "prix_achat_fc" not in details_cols:
        cur.execute(
            "ALTER TABLE vente_details ADD COLUMN prix_achat_fc REAL DEFAULT 0"
        )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            heure TEXT NOT NULL,
            operation TEXT NOT NULL,
            reference TEXT,
            description TEXT,
            montant REAL DEFAULT 0
        )
    """)

    # Historique technique complémentaire : il permet de retracer
    # les opérations importantes et l'état de la base dans le temps.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            horodatage TEXT NOT NULL,
            operation TEXT NOT NULL,
            reference TEXT,
            description TEXT,
            montant REAL DEFAULT 0,
            etat_json TEXT
        )
    """)

    # ========================================================
    # RÉQUISITIONS D'ACHATS
    # ========================================================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS requisitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_requisition TEXT NOT NULL UNIQUE,
            date TEXT NOT NULL,
            heure TEXT NOT NULL,
            total_fc REAL DEFAULT 0,
            total_usd REAL DEFAULT 0,
            statut TEXT DEFAULT 'EN ATTENTE'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS requisition_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requisition_id INTEGER NOT NULL,
            produit_id INTEGER NOT NULL,
            produit TEXT NOT NULL,
            quantite REAL DEFAULT 0,
            prix_achat_usd REAL DEFAULT 0,
            prix_achat_fc REAL DEFAULT 0,
            total_usd REAL DEFAULT 0,
            total_fc REAL DEFAULT 0,
            declaration_fc_unitaire REAL DEFAULT 0,
            total_declaration_fc REAL DEFAULT 0,
            total_general_fc REAL DEFAULT 0,
            FOREIGN KEY (requisition_id)
                REFERENCES requisitions(id)
                ON DELETE CASCADE,
            FOREIGN KEY (produit_id)
                REFERENCES produits(id)
        )
    """)

    # --------------------------------------------------------
    # Frais de déclaration : ajoutés sans modifier les
    # anciennes colonnes ni les anciennes réquisitions.
    # --------------------------------------------------------
    cur.execute("PRAGMA table_info(requisitions)")
    requisitions_cols = [ligne[1] for ligne in cur.fetchall()]
    if "total_declaration_fc" not in requisitions_cols:
        cur.execute(
            "ALTER TABLE requisitions ADD COLUMN total_declaration_fc REAL DEFAULT 0"
        )
    if "total_general_fc" not in requisitions_cols:
        cur.execute(
            "ALTER TABLE requisitions ADD COLUMN total_general_fc REAL DEFAULT 0"
        )
    if "total_transport_fc" not in requisitions_cols:
        cur.execute(
            "ALTER TABLE requisitions ADD COLUMN total_transport_fc REAL DEFAULT 0"
        )

    # Transport calculé après l'enregistrement de la réquisition.
    # Une ligne conserve le prix de transport par unité et son total.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transport_requisition_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            requisition_id INTEGER NOT NULL,
            requisition_detail_id INTEGER NOT NULL,
            produit TEXT NOT NULL,
            quantite REAL DEFAULT 0,
            transport_fc_unitaire REAL DEFAULT 0,
            total_transport_fc REAL DEFAULT 0,
            FOREIGN KEY (requisition_id) REFERENCES requisitions(id) ON DELETE CASCADE,
            FOREIGN KEY (requisition_detail_id) REFERENCES requisition_details(id) ON DELETE CASCADE,
            UNIQUE(requisition_detail_id)
        )
    """)

    cur.execute("PRAGMA table_info(requisition_details)")
    requisition_details_cols = [ligne[1] for ligne in cur.fetchall()]
    if "declaration_fc_unitaire" not in requisition_details_cols:
        cur.execute(
            "ALTER TABLE requisition_details ADD COLUMN declaration_fc_unitaire REAL DEFAULT 0"
        )
    if "total_declaration_fc" not in requisition_details_cols:
        cur.execute(
            "ALTER TABLE requisition_details ADD COLUMN total_declaration_fc REAL DEFAULT 0"
        )
    if "total_general_fc" not in requisition_details_cols:
        cur.execute(
            "ALTER TABLE requisition_details ADD COLUMN total_general_fc REAL DEFAULT 0"
        )

    # ========================================================
    # GESTION DES CRÉDITS
    # ========================================================
    # Module ajouté sans modifier les tables existantes.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS credits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL UNIQUE,
            client TEXT NOT NULL,
            date TEXT NOT NULL,
            echeance TEXT,
            montant_total REAL DEFAULT 0,
            montant_paye REAL DEFAULT 0,
            solde REAL DEFAULT 0,
            statut TEXT DEFAULT 'EN COURS',
            observation TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS credit_paiements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            credit_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            heure TEXT NOT NULL,
            montant REAL DEFAULT 0,
            mode_paiement TEXT DEFAULT 'ESPÈCES',
            observation TEXT DEFAULT '',
            FOREIGN KEY (credit_id) REFERENCES credits(id) ON DELETE CASCADE
        )
    """)

    # Migration : numéro de téléphone / numéro du client.
    # Les anciennes données restent compatibles.
    cur.execute("PRAGMA table_info(credits)")
    colonnes_credits = {row[1] for row in cur.fetchall()}
    if "numero_client" not in colonnes_credits:
        cur.execute(
            "ALTER TABLE credits ADD COLUMN numero_client TEXT DEFAULT ''"
        )

    conn.commit()
    conn.close()


# ============================================================
# OUTILS
# ============================================================

def obtenir_taux():
    conn = connexion()
    cur = conn.cursor()
    cur.execute("SELECT valeur FROM parametres WHERE cle = 'taux_usd'")
    resultat = cur.fetchone()
    conn.close()

    if resultat is None:
        return TAUX_USD_DEFAUT

    try:
        return float(resultat[0])
    except Exception:
        return TAUX_USD_DEFAUT


def enregistrer_taux(taux):
    conn = connexion()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO parametres (cle, valeur) VALUES (?, ?)",
        ("taux_usd", str(taux))
    )
    conn.commit()
    conn.close()


def formater_nombre(valeur):
    try:
        valeur = float(valeur)
        if valeur.is_integer():
            return f"{int(valeur):,}".replace(",", " ")
        return f"{valeur:,.2f}".replace(",", " ")
    except Exception:
        return str(valeur)


def convertir_nombre(valeur):
    valeur = str(valeur).strip().replace(" ", "")
    if not valeur:
        return 0
    return float(valeur.replace(",", "."))


def calculer_usd(prix_fc):
    taux = obtenir_taux()
    return prix_fc / taux if taux > 0 else 0


def calculer_etat(stock):
    try:
        stock = float(stock or 0)
    except Exception:
        stock = 0

    if stock <= 0:
        return "RUPTURE DE STOCK"
    if stock < 10:
        return "STOCK FAIBLE"
    return "OK"


def maintenant():
    return datetime.now()


def resume_base(conn):
    """Retourne un résumé chiffré de toutes les tables présentes."""
    cur = conn.cursor()
    resume = {}
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    tables = [ligne[0] for ligne in cur.fetchall()]
    for nom in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{nom}"')
            resume[nom] = cur.fetchone()[0]
        except Exception:
            resume[nom] = None
    return resume


def enregistrer_audit_conn(conn, operation, reference="", description="", montant=0):
    """Ajoute une trace technique avec le nombre de lignes de chaque table."""
    dt = maintenant()
    etat = resume_base(conn)
    conn.execute("""
        INSERT INTO audit_events
        (horodatage, operation, reference, description, montant, etat_json)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        dt.strftime("%Y-%m-%d %H:%M:%S"),
        operation,
        reference,
        description,
        float(montant or 0),
        json.dumps(etat, ensure_ascii=False, sort_keys=True),
    ))


def enregistrer_journal(operation, reference="", description="", montant=0):
    dt = maintenant()
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO journal
        (date, heure, operation, reference, description, montant)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        dt.strftime("%d/%m/%Y"),
        dt.strftime("%H:%M:%S"),
        operation,
        reference,
        description,
        float(montant or 0)
    ))
    enregistrer_audit_conn(
        conn, operation, reference, description, montant
    )
    conn.commit()
    conn.close()


def date_sql_vers_affichage(valeur):
    try:
        return datetime.strptime(valeur, "%d/%m/%Y").strftime("%d/%m/%Y")
    except Exception:
        return valeur


# ============================================================
# LICENCES
# ============================================================

def signature_licence(type_licence):
    return hmac.new(
        LICENSE_SECRET.encode("utf-8"),
        type_licence.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()[:12].upper()


def valider_cle_licence(cle):
    cle = cle.strip().upper()
    if cle == CLE_TRIAL_30 and hmac.compare_digest(
        signature_licence("TRIAL30"), CLE_TRIAL_30.rsplit("-", 1)[1]
    ):
        return "TRIAL30"
    if cle == CLE_VIE and hmac.compare_digest(
        signature_licence("LIFETIME"), CLE_VIE.rsplit("-", 1)[1]
    ):
        return "LIFETIME"
    return None


def charger_licence():
    if not LICENSE_FILE.exists():
        return None
    try:
        return json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def enregistrer_licence(type_licence):
    maintenant_licence = datetime.now()
    donnees = {
        "type": type_licence,
        "activee_le": maintenant_licence.isoformat(timespec="seconds"),
        "derniere_utilisation": maintenant_licence.isoformat(timespec="seconds"),
        "version": 1,
    }
    LICENSE_FILE.write_text(
        json.dumps(donnees, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return donnees


def licence_valide():
    licence = charger_licence()
    if not licence:
        return False, "Aucune licence activée."

    type_licence = licence.get("type")
    if type_licence not in ("TRIAL30", "LIFETIME"):
        return False, "Licence invalide."

    maintenant_licence = datetime.now()
    try:
        derniere = datetime.fromisoformat(licence.get("derniere_utilisation", ""))
        activee = datetime.fromisoformat(licence.get("activee_le", ""))
    except Exception:
        return False, "Licence corrompue."

    # Protection simple contre un retour de l'horloge.
    if maintenant_licence < derniere:
        return False, "La date/heure de l'ordinateur semble avoir été reculée."

    if type_licence == "TRIAL30":
        expiration = activee + timedelta(days=30)
        if maintenant_licence >= expiration:
            return False, (
                "La licence d'essai de 30 jours a expiré le "
                + expiration.strftime("%d/%m/%Y")
                + "."
            )

    licence["derniere_utilisation"] = maintenant_licence.isoformat(timespec="seconds")
    try:
        LICENSE_FILE.write_text(
            json.dumps(licence, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

    if type_licence == "LIFETIME":
        return True, "Licence à vie active."

    expiration = activee + timedelta(days=30)
    jours_restants = max(0, (expiration.date() - maintenant_licence.date()).days)
    return True, f"Licence d'essai valide — {jours_restants} jour(s) restant(s)."


def demander_licence():
    while True:
        cle, ok = QInputDialog.getText(
            fenetre if "fenetre" in globals() else None,
            "Activation de Billy-eLBERT STOCK",
            "Entrez votre clé de licence :"
        )
        if not ok:
            return False

        type_licence = valider_cle_licence(cle)
        if type_licence:
            enregistrer_licence(type_licence)
            return True

        QMessageBox.warning(
            fenetre if "fenetre" in globals() else None,
            "Licence",
            "Clé de licence incorrecte."
        )


def changer_licence():
    """Permet de remplacer la licence actuelle pendant l'utilisation."""
    actuelle = charger_licence() or {}
    type_actuel = actuelle.get("type")

    if type_actuel == "LIFETIME":
        confirmation = QMessageBox.question(
            fenetre,
            "Changer de licence",
            "Une licence à vie est actuellement active.\n\n"
            "Voulez-vous vraiment la remplacer par une autre licence ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return

    cle, ok = QInputDialog.getText(
        fenetre,
        "Changer de licence",
        "Entrez la nouvelle clé de licence :"
    )

    if not ok:
        return

    type_licence = valider_cle_licence(cle)

    if not type_licence:
        QMessageBox.warning(
            fenetre,
            "Licence",
            "Clé de licence incorrecte.\n\n"
            "La licence actuelle reste inchangée."
        )
        return

    enregistrer_licence(type_licence)
    activer_interface_apres_licence()
    mettre_a_jour_compteur_licence()

    if type_licence == "LIFETIME":
        texte = "Licence à vie activée avec succès."
    else:
        _, message = licence_valide()
        texte = "Licence d'essai activée avec succès.\n\n" + message

    QMessageBox.information(
        fenetre,
        "Licence",
        texte
    )


def charger_essai_gratuit():
    """Charge la date de début de l'essai gratuit de 30 jours."""
    if not TRIAL_FILE.exists():
        return None

    try:
        donnees = json.loads(TRIAL_FILE.read_text(encoding="utf-8"))
        debut = datetime.fromisoformat(donnees.get("debut", ""))
        return debut
    except Exception:
        return None


def initialiser_essai_gratuit():
    """Crée une seule fois le début de l'essai gratuit."""
    debut = charger_essai_gratuit()
    if debut is not None:
        return debut

    debut = datetime.now()
    donnees = {
        "debut": debut.isoformat(timespec="seconds"),
        "duree_jours": TRIAL_DUREE_JOURS,
        "version": 1,
    }

    try:
        TRIAL_FILE.write_text(
            json.dumps(donnees, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass

    return debut


def essai_gratuit_valide():
    """Retourne l'état de l'essai gratuit et le nombre de jours restants."""
    debut = initialiser_essai_gratuit()
    maintenant_essai = datetime.now()

    if maintenant_essai < debut:
        return False, 0, "La date/heure de l'ordinateur semble incorrecte."

    expiration = debut + timedelta(days=TRIAL_DUREE_JOURS)

    if maintenant_essai >= expiration:
        return False, 0, (
            "Votre essai gratuit de 30 jours a expiré le "
            + expiration.strftime("%d/%m/%Y")
            + "."
        )

    jours_restants = max(
        0,
        (expiration.date() - maintenant_essai.date()).days
    )

    return True, jours_restants, (
        f"Essai gratuit : {jours_restants} jour(s) restant(s)."
    )


def obtenir_texte_compteur_licence():
    """Texte du compteur affiché dans le menu."""
    valide, message = licence_valide()

    if valide:
        licence = charger_licence() or {}
        if licence.get("type") == "LIFETIME":
            return ""

        type_licence = licence.get("type")
        if type_licence == "TRIAL30":
            try:
                activee = datetime.fromisoformat(licence.get("activee_le", ""))
                expiration = activee + timedelta(days=30)
                jours = max(
                    0,
                    (expiration.date() - datetime.now().date()).days
                )
                return f"Licence d'essai : {jours} jour(s) restant(s)."
            except Exception:
                return message

    if TRIAL_FILE.exists():
        essai_ok, jours, _ = essai_gratuit_valide()
        if essai_ok:
            return f"Essai gratuit : {jours} jour(s) restant(s)."

        return "Essai gratuit expiré — licence requise"

    return "Activation requise — essai gratuit 30 jours disponible"


def verifier_acces_licence():
    """
    Vérifie l'accès sans fermer la fenêtre.
    Les boutons restent désactivés tant qu'une licence ou un essai valide
    n'est pas disponible.
    """
    valide, _ = licence_valide()

    if valide:
        return True

    # Si aucun essai n'a encore été commencé, l'application reste verrouillée
    # jusqu'au choix explicite "ESSAI GRATUIT 30 JOURS".
    if TRIAL_FILE.exists():
        essai_ok, _, _ = essai_gratuit_valide()
        if essai_ok:
            return True

    return False


def demander_activation_ou_essai():
    """
    Affiche le choix d'activation lorsque la fenêtre est déjà visible.
    Le bouton ESSAI GRATUIT démarre/valide l'essai de 30 jours.
    """
    valide, message = licence_valide()
    if valide:
        return True

    if TRIAL_FILE.exists():
        essai_ok, jours, message_essai = essai_gratuit_valide()
        if essai_ok:
            return True
    else:
        jours = TRIAL_DUREE_JOURS
        message_essai = "L'essai gratuit de 30 jours n'a pas encore été démarré."

    choix = QMessageBox(fenetre)
    choix.setWindowTitle("Activation de Billy-eLBERT STOCK")
    choix.setText(
        "L'application est verrouillée.\n\n"
        "Activez une licence à vie ou utilisez l'essai gratuit de 30 jours."
    )
    choix.setInformativeText(
        message_essai + "\n\n"
        "Vous pouvez également entrer une clé de licence."
    )

    bouton_essai = choix.addButton(
        "ESSAI GRATUIT 30 JOURS",
        QMessageBox.AcceptRole
    )
    bouton_cle = choix.addButton(
        "ENTRER UNE CLÉ",
        QMessageBox.ActionRole
    )
    choix.addButton(
        "QUITTER",
        QMessageBox.RejectRole
    )

    choix.exec()

    if choix.clickedButton() == bouton_essai:
        if not TRIAL_FILE.exists():
            initialiser_essai_gratuit()

        essai_ok, _, message_essai = essai_gratuit_valide()
        if essai_ok:
            return True

        QMessageBox.warning(
            fenetre,
            "Essai expiré",
            message_essai
        )
        return False

    if choix.clickedButton() == bouton_cle:
        return demander_licence()

    return False


def activer_interface_apres_licence():
    """Active tous les boutons du menu après activation réussie."""
    for bouton in (
        bouton_tableau,
        bouton_produits,
        bouton_stock,
        bouton_achats,
        bouton_ventes,
        bouton_statistiques,
        bouton_finance,
        bouton_credits,
        bouton_journal_audit,
        bouton_parametres,
        ):
        bouton.setEnabled(True)

    mettre_a_jour_compteur_licence()


def verrouiller_interface():
    """Désactive tous les boutons du menu avant activation."""
    for bouton in (
        bouton_tableau,
        bouton_produits,
        bouton_stock,
        bouton_achats,
        bouton_ventes,
        bouton_statistiques,
        bouton_finance,
        bouton_credits,
        bouton_journal_audit,
        bouton_parametres,
        ):
        bouton.setEnabled(False)


def mettre_a_jour_compteur_licence():
    if "label_compteur_licence" not in globals():
        return

    texte = obtenir_texte_compteur_licence()
    label_compteur_licence.setText(texte)

    if texte:
        label_compteur_licence.show()
    else:
        label_compteur_licence.hide()


def verifier_licence_apres_ouverture():
    """Lance l'activation une fois la fenêtre visible."""
    if verifier_acces_licence():
        activer_interface_apres_licence()
        return

    verrouiller_interface()

    if demander_activation_ou_essai():
        activer_interface_apres_licence()
    else:
        mettre_a_jour_compteur_licence()


# ============================================================
# SAUVEGARDE COMPLÈTE / TRAÇABILITÉ
# ============================================================

def calculer_sha256(fichier):
    h = hashlib.sha256()
    with open(fichier, "rb") as flux:
        for bloc in iter(lambda: flux.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


def enregistrer_etat_complet():
    """Archive toute la base et prépare les données initiales de l'EXE final."""
    if not demander_mot_de_passe():
        return

    try:
        # S'assurer que toutes les transactions sont terminées.
        conn = connexion()
        conn.commit()
        enregistrer_audit_conn(
            conn,
            "SAUVEGARDE ÉTAT COMPLET",
            "",
            "Sauvegarde manuelle complète avant préparation de l'EXE final.",
            0
        )
        conn.commit()
        conn.close()

        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_db = ARCHIVES_DIR / f"stock_{horodatage}.db"
        shutil.copy2(BASE, archive_db)

        manifeste = {
            "horodatage": datetime.now().isoformat(timespec="seconds"),
            "mode_avant": "FINAL" if MODE_FINAL else "DEMO",
            "base_archive": archive_db.name,
            "sha256": calculer_sha256(archive_db),
            "licence": charger_licence(),
            "tables": {},
        }

        conn = sqlite3.connect(archive_db)
        manifeste["tables"] = resume_base(conn)
        conn.close()

        (ARCHIVES_DIR / f"etat_{horodatage}.json").write_text(
            json.dumps(manifeste, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        # En mode démo, cette copie devient le stock initial qui sera
        # embarqué dans l'EXE final. Le prochain EXE final sera persistant.
        if not MODE_FINAL:
            shutil.copy2(BASE, INITIAL_DB)
            MODE_FINAL_FLAG.write_text(
                "EXE FINAL — données initiales préparées le "
                + datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                encoding="utf-8"
            )

        QMessageBox.information(
            fenetre,
            "SAUVEGARDE COMPLÈTE",
            "Toutes les données ont été enregistrées.\n\n"
            "Archive : " + archive_db.name + "\n\n"
            + (
                "Les données initiales de l'EXE final sont prêtes.\n"
                "Vous pouvez maintenant générer l'EXE final."
                if not MODE_FINAL
                else "L'état actuel de l'EXE final a été archivé avec succès."
            )
        )

    except Exception as erreur:
        QMessageBox.critical(
            fenetre,
            "SAUVEGARDE",
            "La sauvegarde complète a échoué :\n\n" + str(erreur)
        )


def supprimer_audits():
    """Supprime toutes les traces de la table audit_events après authentification."""
    mot_de_passe, ok = QInputDialog.getText(
        fenetre,
        "SUPPRESSION DES AUDITS",
        "Mot de passe administrateur :",
        QLineEdit.EchoMode.Password
    )
    if not ok:
        return

    if not hmac.compare_digest(mot_de_passe, MOT_DE_PASSE_ADMIN):
        QMessageBox.warning(
            fenetre,
            "ACCÈS REFUSÉ",
            "Mot de passe administrateur incorrect."
        )
        return

    confirmation = QMessageBox.question(
        fenetre,
        "CONFIRMATION",
        "Voulez-vous vraiment supprimer toutes les traces d'audit ?\n\n"
        "Cette opération effacera définitivement les événements de la table "
        "TRAÇABILITÉ / AUDIT.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if confirmation != QMessageBox.StandardButton.Yes:
        return

    try:
        conn = connexion()
        conn.execute("DELETE FROM audit_events")
        conn.commit()
        conn.close()
        QMessageBox.information(
            fenetre,
            "AUDIT SUPPRIMÉ",
            "Toutes les traces d'audit ont été supprimées."
        )
        afficher_historique_audit()
    except Exception as exc:
        QMessageBox.critical(
            fenetre,
            "ERREUR",
            f"Impossible de supprimer les audits :\n{exc}"
        )


def afficher_historique_audit():
    nettoyer_zone()
    contenu.addWidget(creer_titre("TRAÇABILITÉ / AUDIT", 30))

    info = QLabel(
        "Les opérations importantes sont conservées avec leur date, heure et état de la base. "
        "Les archives complètes sont placées dans le dossier 'archives'."
    )
    info.setStyleSheet("font-size: 14px; padding: 8px;")
    contenu.addWidget(info)

    barre_audit = QHBoxLayout()
    barre_audit.addStretch()
    bouton_supprimer_audit = QPushButton("🗑️ SUPPRIMER LES AUDITS")
    bouton_supprimer_audit.setMinimumHeight(38)
    bouton_supprimer_audit.setToolTip("Supprimer toutes les traces d'audit — mot de passe administrateur requis")
    bouton_supprimer_audit.setStyleSheet("""
        QPushButton {
            background: #FCE8E8;
            color: #B42318;
            border: 1px solid #F2B8B5;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 800;
        }
        QPushButton:hover { background: #F9D5D3; border-color: #D92D20; }
    """)
    bouton_supprimer_audit.clicked.connect(supprimer_audits)
    barre_audit.addWidget(bouton_supprimer_audit)
    contenu.addLayout(barre_audit)

    tableau = QTableWidget()
    tableau.setColumnCount(7)
    tableau.setHorizontalHeaderLabels([
        "ID", "DATE / HEURE", "OPÉRATION", "RÉFÉRENCE",
        "DESCRIPTION", "MONTANT", "ÉTAT"
    ])
    appliquer_tableau_standard(tableau)
    contenu.addWidget(tableau)

    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, horodatage, operation, reference, description, montant, etat_json
        FROM audit_events
        ORDER BY id DESC
    """)
    lignes = cur.fetchall()
    conn.close()

    tableau.setRowCount(len(lignes))
    for row, ligne in enumerate(lignes):
        try:
            etat = json.loads(ligne[6] or "{}")
            resume = ", ".join(f"{k}: {v}" for k, v in etat.items())
        except Exception:
            resume = ligne[6] or ""
        ajouter_ligne_tableau(tableau, row, [
            ligne[0], ligne[1], ligne[2], ligne[3] or "",
            ligne[4] or "", formater_nombre(ligne[5]) + " FC", resume
        ])


# ============================================================
# BOUTON SIMPLE / DOUBLE CLIC
# ============================================================

class BoutonMasquerReafficher(QPushButton):
    def __init__(self, texte="", parent=None):
        super().__init__(texte, parent)

        self.timer_clic = QTimer(self)
        self.timer_clic.setSingleShot(True)
        self.timer_clic.setInterval(250)

        self.action_simple_clic = None
        self.action_double_clic = None

        self.timer_clic.timeout.connect(self.executer_simple_clic)

    def executer_simple_clic(self):
        if self.action_simple_clic:
            self.action_simple_clic()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.timer_clic.start()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.timer_clic.stop()
            if self.action_double_clic:
                self.action_double_clic()
        super().mouseDoubleClickEvent(event)


# ============================================================
# RÉINITIALISATION COMPLÈTE DE L'APPLICATION
# ============================================================
def reinitialiser_application():
    """Efface toutes les données métier de la base active sans toucher à la licence."""
    mot, ok = QInputDialog.getText(
        fenetre,
        "RÉINITIALISER L'APPLICATION",
        "Mot de passe de réinitialisation :",
        QLineEdit.EchoMode.Password
    )

    if not ok:
        return

    if mot != "Gaïl2025":
        QMessageBox.warning(
            fenetre,
            "ACCÈS REFUSÉ",
            "Mot de passe incorrect."
        )
        return

    confirmation = QMessageBox.question(
        fenetre,
        "CONFIRMATION",
        "ATTENTION !\n\n"
        "Cette opération va remettre l'application à zéro :\n"
        "• produits et stocks\n"
        "• ventes et détails des ventes\n"
        "• réquisitions et détails des réquisitions\n"
        "• journal et traçabilité / audit\n\n"
        "La licence, l'essai, le programme et les archives ne seront PAS supprimés.\n\n"
        "Voulez-vous vraiment continuer ?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )

    if confirmation != QMessageBox.StandardButton.Yes:
        return

    tables = [
        "credit_paiements",
        "credits",
        "vente_details",
        "ventes",
        "requisition_details",
        "requisitions",
        "journal",
        "audit_events",
        "produits",
    ]

    try:
        conn = connexion()
        cur = conn.cursor()

        for table_nom in tables:
            cur.execute(f"DELETE FROM {table_nom}")

        # Remettre les compteurs ID à zéro.
        placeholders = ",".join("?" for _ in tables)
        cur.execute(
            f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
            tables
        )

        # Le taux de change de départ reste 1 USD = 2250 FC.
        cur.execute(
            "INSERT OR REPLACE INTO parametres (cle, valeur) VALUES (?, ?)",
            ("taux_usd", str(TAUX_USD_DEFAUT))
        )

        conn.commit()
        conn.close()

        QMessageBox.information(
            fenetre,
            "RÉINITIALISATION TERMINÉE",
            "L'application a été remise à zéro avec succès.\n\n"
            "La licence et l'essai ont été conservés."
        )

        afficher_accueil()

    except Exception as erreur:
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        QMessageBox.critical(
            fenetre,
            "ERREUR",
            "La réinitialisation n'a pas pu être terminée.\n\n"
            + str(erreur)
        )


# ============================================================
# APPLICATION
# ============================================================

app = QApplication(sys.argv)
app.setStyleSheet(r"""
QWidget { font-family: "Segoe UI"; font-size: 13px; color: #415A70; }
QMainWindow, QWidget { background-color: #EEF2F6; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    min-height: 34px; background: #FFFFFF; border: 1px solid #CBD5E1;
    border-radius: 8px; padding: 4px 10px;
    selection-background-color: #2563EB; selection-color: #FFFFFF;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QDateEdit:focus { border: 2px solid #2563EB; }
QPushButton {
    min-height: 34px; background: #FFFFFF; color: #415A70;
    border: 1px solid #CBD5E1; border-radius: 8px;
    padding: 5px 14px; font-weight: 600;
}
QPushButton:hover { background: #EFF6FF; border-color: #93C5FD; }
QPushButton:pressed { background: #DBEAFE; }
QPushButton:disabled { background: #E5E7EB; color: #9CA3AF; border-color: #D1D5DB; }
QTableWidget {
    background: #FFFFFF; alternate-background-color: #F1F5F9;
    border: 1px solid #CBD5E1; border-radius: 10px;
    gridline-color: #D9E1EA; selection-background-color: #1D4ED8;
    selection-color: #FFFFFF; color: #1F2937;
}
QTableWidget::item { padding: 7px; color: #1F2937; background: #FFFFFF; }
QTableWidget::item:alternate { background: #F1F5F9; color: #1F2937; }
QTableWidget::item:selected { background: #1D4ED8; color: #FFFFFF; font-weight: 800; }
QTableWidget::item:selected:alternate { background: #1D4ED8; color: #FFFFFF; font-weight: 800; }
QHeaderView::section {
    background: #334155; color: #FFFFFF; border: none;
    padding: 9px 6px; font-weight: 800;
}
QTabWidget::pane {
    border: 1px solid #E2E8F0; background: #FFFFFF;
    border-radius: 10px; top: -1px;
}
QTabBar::tab {
    background: #E2E8F0; color: #334155; padding: 9px 16px;
    margin-right: 2px; border-top-left-radius: 7px; border-top-right-radius: 7px;
}
QTabBar::tab:selected { background: #2563EB; color: #FFFFFF; font-weight: 700; }
QTabBar::tab:hover { background: #BFDBFE; color: #415A70; }
QGroupBox {
    background: #FFFFFF; border: 1px solid #E2E8F0;
    border-radius: 10px; margin-top: 12px; padding: 12px; font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 12px; padding: 0 6px;
    color: #3B556D; background: #EEF2F6;
}
QScrollBar:vertical {
    background: #EEF2F7; width: 10px; margin: 2px; border-radius: 5px;
}
QScrollBar::handle:vertical { background: #94A3B8; min-height: 30px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #64748B; }
QScrollBar:horizontal {
    background: #EEF2F7; height: 10px; margin: 2px; border-radius: 5px;
}
QScrollBar::handle:horizontal { background: #94A3B8; min-width: 30px; border-radius: 5px; }
QToolTip {
    background: #334155; color: #FFFFFF; border: 1px solid #334155;
    padding: 6px 8px; border-radius: 5px;
}
QMessageBox, QDialog { background: #EEF2F6; }
""")
# ============================================================
# LOGO DE L'APPLICATION
# ============================================================

logo_path = LOGO_PATH

print("LOGO :", logo_path)
print("LOGO EXISTE :", logo_path.exists())

if logo_path.exists():
    icone_application = QIcon(str(logo_path))
    app.setWindowIcon(icone_application)

creer_base()

fenetre = QWidget()
fenetre.setWindowTitle("Billy-eLBERT STOCK")
fenetre.resize(1350, 800)

if logo_path.exists():
    fenetre.setWindowIcon(icone_application)

if ANDROID:
    # Sur téléphone/tablette, Qt utilise l'espace disponible.
    # Aucun changement de taille n'est imposé.
    fenetre.showMaximized()
else:
    fenetre.resize(1350, 800)

principal = QHBoxLayout(fenetre)

# ============================================================
# MENU
# ============================================================

menu_widget = QWidget()
menu_widget.setFixedWidth(250)
menu = QVBoxLayout(menu_widget)

titre = QLabel("GESTION STOCK")
titre.setStyleSheet("""
    font-size: 22px;
    font-weight: 800;
    padding: 10px;
    color: #29465B;
""")
menu.addWidget(titre)
mode_label = QLabel("MODE FINAL" if MODE_FINAL else "MODE DÉMONSTRATION")
mode_label.setStyleSheet("font-size: 11px; font-weight: bold; padding: 4px; color: #607080;")
menu.addWidget(mode_label)

label_compteur_licence = QLabel("")
label_compteur_licence.setAlignment(Qt.AlignmentFlag.AlignCenter)
label_compteur_licence.setWordWrap(True)
label_compteur_licence.setStyleSheet(
    "font-size: 11px; font-weight: bold; padding: 6px; color: #555;"
)
menu.addWidget(label_compteur_licence)

bouton_changer_licence = QPushButton("🔑  CHANGER DE LICENCE")
bouton_changer_licence.setToolTip(
    "Remplacer la licence actuelle par une nouvelle clé"
)
bouton_changer_licence.clicked.connect(changer_licence)
menu.addWidget(bouton_changer_licence)

if ANDROID:
    android_label = QLabel("ANDROID / APK")
    android_label.setStyleSheet(
        "font-size: 10px; font-weight: bold; padding: 2px; color: #555;"
    )
    menu.addWidget(android_label)

class RubriqueMenu(QLabel):
    """Rubrique de menu non-bouton, cliquable pour ouvrir À propos."""
    def __init__(self, texte, callback, parent=None):
        super().__init__(texte, parent)
        self._callback = callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(36)
        self.setStyleSheet("""
            QLabel {
                color: #526173;
                background: transparent;
                border-top: 1px solid #D7E0EA;
                border-bottom: 1px solid #D7E0EA;
                padding: 8px 6px;
                font-size: 11px;
                font-weight: 800;
            }
            QLabel:hover {
                color: #0F766E;
                background: #EEF8F6;
            }
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._callback:
            self._callback()
        super().mousePressEvent(event)


bouton_tableau = QPushButton("📊  TABLEAU DE BORD")
bouton_produits = QPushButton("📦  PRODUITS")
bouton_stock = QPushButton("🏭  STOCK")
bouton_achats = QPushButton("🛒  ACHATS")
bouton_ventes = QPushButton("💰  VENTES")
bouton_statistiques = QPushButton("📈  STATISTIQUES")
bouton_finance = QPushButton("💳  FINANCE")
bouton_credits = QPushButton("💳  GESTION DES CRÉDITS")
bouton_journal_audit = QPushButton("🛡️  TRAÇABILITÉ / AUDIT")
bouton_parametres = QPushButton("⚙️  PARAMÈTRES")

# Rubrique non-bouton : À propos du concepteur.
rubrique_apropos = RubriqueMenu("👨‍💻  À PROPOS DU CONCEPTEUR", lambda: afficher_a_propos())

# Bouton auxiliaire réservé à l'administrateur.
bouton_reinitialiser = QPushButton("🔴 RÉINITIALISER L'APPLICATION")
bouton_reinitialiser.setToolTip(
    "Remettre toutes les données métier à zéro avec le mot de passe Gaïl2025"
)
bouton_reinitialiser.clicked.connect(reinitialiser_application)

for bouton in (
    bouton_tableau,
    bouton_produits,
    bouton_stock,
    bouton_achats,
    bouton_ventes,
    bouton_statistiques,
    bouton_finance,
    bouton_credits,
    bouton_journal_audit,
    bouton_parametres,
    bouton_reinitialiser,
):
    menu.addWidget(bouton)

menu.addSpacing(8)
menu.addWidget(rubrique_apropos)

def appliquer_couleurs_menu():
    """Applique une couleur distincte à chaque rubrique du menu principal."""
    couleurs = {
        bouton_tableau: ("#DCEBFF", "#2457A6"),
        bouton_produits: ("#DFF3E8", "#18794E"),
        bouton_stock: ("#DDF1F4", "#176B78"),
        bouton_achats: ("#FFF0D8", "#9A5B13"),
        bouton_ventes: ("#EAE3FA", "#5C469C"),
        bouton_statistiques: ("#DDEFF2", "#176B78"),
        bouton_finance: ("#DDEFE8", "#176A4A"),
        bouton_credits: ("#E0F2FE", "#0369A1"),
        bouton_journal_audit: ("#F8E1E1", "#A43A3A"),
        bouton_parametres: ("#E5EAF0", "#455468"),
        bouton_reinitialiser: ("#F8E1E1", "#A43A3A"),
        bouton_changer_licence: ("#EDE3F7", "#65428A"),
    }

    for bouton, (fond, texte) in couleurs.items():
        bouton.setStyleSheet(f"""
            QPushButton {{
                background-color: {fond};
                color: {texte};
                border: 1px solid rgba(100,116,139,0.16);
                border-radius: 8px;
                padding: 9px 8px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #FFFFFF;
                border-color: {texte};
            }}
            QPushButton:pressed {{
                background-color: #E8EEF5;
            }}
            QPushButton:disabled {{
                background-color: #E9EDF2;
                color: #9AA5B1;
                border-color: #D8DEE6;
            }}
        """)


appliquer_couleurs_menu()

menu.addStretch()

# Au premier affichage, toutes les commandes restent verrouillées
# jusqu'à l'activation de la licence ou de l'essai gratuit.
verrouiller_interface()

# ============================================================
# ZONE CENTRALE
# ============================================================

contenu_widget = QWidget()
contenu = QVBoxLayout(contenu_widget)
contenu.setContentsMargins(15, 15, 15, 15)

# ============================================================
# VARIABLES
# ============================================================

table = None
champ_recherche = None
txt_produit = None
txt_prix_fc = None
txt_prix_usd = None
txt_prix_achat_fc = None
txt_stock = None
txt_expiration = None
titre_mode = None
bouton_masquer = None

table_ventes = None
champ_recherche_vente = None
panier_vente = []
table_panier_vente = None
spin_quantite_vente = None
label_total_fc_vente = None
label_total_usd_vente = None


# ============================================================
# OUTILS UI
# ============================================================

def nettoyer_zone():
    global table, champ_recherche, txt_produit, txt_prix_fc
    global txt_prix_usd, txt_prix_achat_fc, txt_stock
    global txt_expiration, titre_mode, bouton_masquer

    while contenu.count() > 0:
        element = contenu.takeAt(0)
        widget = element.widget()

        if widget is not None:
            widget.deleteLater()
        else:
            layout = element.layout()
            if layout is not None:
                while layout.count() > 0:
                    sous = layout.takeAt(0)
                    sous_widget = sous.widget()
                    if sous_widget is not None:
                        sous_widget.deleteLater()

    table = None
    champ_recherche = None
    txt_produit = None
    txt_prix_fc = None
    txt_prix_usd = None
    txt_prix_achat_fc = None
    txt_stock = None
    txt_expiration = None
    titre_mode = None
    bouton_masquer = None


def creer_titre(texte, taille=28):
    label = QLabel(texte)
    label.setStyleSheet(f"""
        QLabel {{
            font-size: {taille}px;
            font-weight: bold;
            padding: 10px;
        }}
    """)
    return label


def creer_carte_dashboard(libelle, valeur, index=0, palette=None):
    """Carte KPI professionnelle avec icône visuelle agrandie."""
    texte = str(libelle).strip()
    morceaux = texte.split(None, 1)
    icone = morceaux[0] if morceaux and any(ord(c) > 127 for c in morceaux[0]) else "•"
    titre = morceaux[1] if len(morceaux) > 1 else texte

    palette_defaut = [
        ("#EAF2FF", "#2F6FED"),
        ("#EAF8F0", "#1F9D68"),
        ("#E8F7F7", "#168A8A"),
        ("#FFF4E5", "#D9822B"),
        ("#F1ECFF", "#7357C7"),
        ("#FCEEF3", "#C64F78"),
    ]
    palette = palette or palette_defaut
    fond, accent = palette[index % len(palette)]

    bloc = QFrame()
    bloc.setMinimumHeight(155)
    bloc.setObjectName("dashboardCard")
    bloc.setStyleSheet(f"""
        QFrame#dashboardCard {{
            background: #FFFFFF;
            border: 1px solid #D7E0EA;
            border-left: 5px solid {accent};
            border-radius: 12px;
        }}
        QFrame#dashboardCard:hover {{
            border: 1px solid {accent};
            border-left: 5px solid {accent};
            background: #FBFDFF;
        }}
    """)

    layout = QVBoxLayout(bloc)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(4)

    icon = QLabel(icone)
    icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon.setMinimumHeight(48)
    icon.setStyleSheet(
        f"background:{fond}; color:{accent}; border-radius:10px;"
        "font-size:32px; font-weight:700; padding:5px;"
    )
    layout.addWidget(icon)

    titre_label = QLabel(titre.upper())
    titre_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    titre_label.setWordWrap(True)
    titre_label.setStyleSheet(
        f"color:#526173; font-size:11px; font-weight:700;"
        "border:none; background:transparent; padding:2px;"
    )
    layout.addWidget(titre_label)

    valeur_label = QLabel(str(valeur))
    valeur_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    valeur_label.setWordWrap(True)
    valeur_label.setStyleSheet(
        f"color:{accent}; font-size:21px; font-weight:800;"
        "border:none; background:transparent; padding:2px;"
    )
    layout.addWidget(valeur_label)
    return bloc


def centrer_tableau(tableau):
    for row in range(tableau.rowCount()):
        for col in range(tableau.columnCount()):
            item = tableau.item(row, col)
            if item:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)


def appliquer_tableau_standard(tableau):
    tableau.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    tableau.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tableau.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tableau.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)


def ajouter_ligne_tableau(tableau, row, valeurs):
    for col, valeur in enumerate(valeurs):
        item = QTableWidgetItem(str(valeur))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        tableau.setItem(row, col, item)


# ============================================================
# GRAPHIQUE PROFESSIONNEL NATIF (sans dépendance externe)
# ============================================================
class GraphiqueVentes(QWidget):
    """Graphique à barres simple, lisible et compatible PySide6."""
    def __init__(self, jours=None, valeurs=None, parent=None, titre=None):
        super().__init__(parent)
        self.titre = titre or "ÉVOLUTION DU CHIFFRE D’AFFAIRES — 7 DERNIERS JOURS"
        self.jours = list(jours or [])
        self.valeurs = [max(0.0, float(v or 0)) for v in (valeurs or [])]
        self.setMinimumHeight(235)
        self.setSizePolicy(self.sizePolicy().Policy.Expanding, self.sizePolicy().Policy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        painter.setPen(QColor("#415A70"))
        titre_font = QFont("Segoe UI", 12, QFont.Weight.Bold)
        painter.setFont(titre_font)
        painter.drawText(20, 27, self.titre)
        left, top, right, bottom = 54, 48, self.width() - 22, self.height() - 35
        largeur = max(1, right - left)
        hauteur = max(1, bottom - top)
        painter.setPen(QPen(QColor("#E2E8F0"), 1))
        for i in range(4):
            y = top + int(hauteur * i / 3)
            painter.drawLine(left, y, right, y)
        maximum = max(self.valeurs or [0]) or 1
        n = max(1, len(self.valeurs))
        espace = largeur / n
        for i, valeur in enumerate(self.valeurs):
            bar_h = int((valeur / maximum) * (hauteur - 22))
            x = int(left + i * espace + espace * 0.22)
            w = max(8, int(espace * 0.56))
            y = bottom - bar_h
            couleur = QColor("#2563EB" if i == len(self.valeurs) - 1 else "#60A5FA")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(couleur)
            painter.drawRoundedRect(x, y, w, max(3, bar_h), 5, 5)
            painter.setPen(QColor("#334155"))
            painter.setFont(QFont("Segoe UI", 8))
            texte = self.jours[i] if i < len(self.jours) else ""
            painter.drawText(int(left + i * espace), bottom + 18, int(espace), 16,
                             Qt.AlignmentFlag.AlignHCenter, texte)
            if valeur > 0:
                montant = (f"{valeur:,.0f}").replace(",", " ")
                painter.drawText(x - 12, max(top + 10, y - 5), w + 24, 15,
                                 Qt.AlignmentFlag.AlignHCenter, montant)
        painter.end()


# ============================================================
# TABLEAU DE BORD PRINCIPAL
# ============================================================
def obtenir_message_accueil_pdf():
    """Retourne le message d'accueil modifiable, utilisé comme nom sur les PDF."""
    fichier = DOSSIER / "message_accueil.txt"
    message_defaut = "Maison Chef-d'œuvres"
    try:
        message = fichier.read_text(encoding="utf-8").strip()
        return message or message_defaut
    except (OSError, UnicodeError):
        return message_defaut


def afficher_accueil():
    nettoyer_zone()

    contenu.addWidget(creer_titre("GESTION STOCK", 30))

    conn = connexion()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM produits WHERE visible = 1")
    nb_produits = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(stock), 0) FROM produits WHERE visible = 1")
    stock_total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM ventes")
    nb_ventes = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(total_fc), 0) FROM ventes")
    ca_total = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM((prix_fc - prix_achat_fc) * quantite), 0)
        FROM vente_details
    """)
    benefice_total = cur.fetchone()[0]

    cur.execute("SELECT date, COALESCE(SUM(total_fc), 0) FROM ventes GROUP BY date")
    ventes_par_date = cur.fetchall()
    conn.close()

    aujourd_hui = date.today()
    jours_graphique = [(aujourd_hui - timedelta(days=6-i)) for i in range(7)]
    index_ventes = {}
    for date_txt, montant in ventes_par_date:
        try:
            d = datetime.strptime(str(date_txt), "%d/%m/%Y").date()
            index_ventes[d] = index_ventes.get(d, 0) + float(montant or 0)
        except (ValueError, TypeError):
            continue
    libelles_graphique = [d.strftime("%d/%m") for d in jours_graphique]
    valeurs_graphique = [index_ventes.get(d, 0) for d in jours_graphique]

    grille = QGridLayout()

    cartes = [
        ("📦  PRODUITS", formater_nombre(nb_produits)),
        ("📊  STOCK TOTAL", formater_nombre(stock_total)),
        ("🧾  NOMBRE DE VENTES", formater_nombre(nb_ventes)),
        ("💰  CHIFFRE D'AFFAIRES", formater_nombre(ca_total) + " FC"),
        ("📈  BÉNÉFICE GLOBAL", formater_nombre(benefice_total) + " FC"),
        ("🏷️  VALEUR STOCK PV", formater_nombre(valeur_stock_pv()) + " FC"),
    ]

    for i, (nom, valeur) in enumerate(cartes):
        grille.addWidget(creer_carte_dashboard(nom, valeur, i), i // 3, i % 3)

    contenu.addLayout(grille)
    graphique = GraphiqueVentes(libelles_graphique, valeurs_graphique)
    graphique.setStyleSheet("background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;")
    contenu.addWidget(graphique)

    # --------------------------------------------------------
    # MESSAGE WORDART EN BAS
    # --------------------------------------------------------

    # Le message d'accueil est personnalisable et conservé entre les démarrages.
    FICHIER_MESSAGE_ACCUEIL = DOSSIER / "message_accueil.txt"
    MESSAGE_ACCUEIL_DEFAUT = "Maison Chef-d'œuvres"

    def lire_message_accueil():
        try:
            valeur = FICHIER_MESSAGE_ACCUEIL.read_text(encoding="utf-8").strip()
            return valeur or MESSAGE_ACCUEIL_DEFAUT
        except (OSError, UnicodeError):
            return MESSAGE_ACCUEIL_DEFAUT

    def modifier_message_accueil():
        mot_de_passe, ok = QInputDialog.getText(
            fenetre, "Protection administrateur", "Mot de passe requis :",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return
        if not hmac.compare_digest(mot_de_passe, "041909"):
            QMessageBox.warning(fenetre, "Accès refusé", "Mot de passe incorrect.")
            return
        nouveau, valide = QInputDialog.getText(
            fenetre, "Modifier le message d'accueil",
            "Saisissez le nouveau message :",
            QLineEdit.EchoMode.Normal, message.text()
        )
        if not valide:
            return
        nouveau = nouveau.strip()
        if not nouveau:
            QMessageBox.warning(fenetre, "Message invalide", "Le message ne peut pas être vide.")
            return
        try:
            FICHIER_MESSAGE_ACCUEIL.write_text(nouveau, encoding="utf-8")
            message.setText(nouveau)
            QMessageBox.information(fenetre, "Message enregistré", "Le message d'accueil a été enregistré.")
        except OSError as exc:
            QMessageBox.critical(fenetre, "Erreur d'enregistrement", f"Impossible d'enregistrer le message :\n{exc}")

    message = QLabel(lire_message_accueil())

    message.setAlignment(
        Qt.AlignmentFlag.AlignCenter
    )

    message.setStyleSheet("""
        QLabel {
            font-size: 28px;
            font-weight: bold;
            color: #1E3A8A;
            padding: 15px;
            border: 3px solid #1E3A8A;
            border-radius: 15px;
            background: #FFFFFF;
        }
    """)

    ombre = QGraphicsDropShadowEffect()

    ombre.setBlurRadius(
        15
    )

    ombre.setOffset(
        3,
        3
    )

    message.setGraphicsEffect(
        ombre
    )

    # Le stretch pousse le message vers le bas
    contenu.addStretch()

    contenu.addWidget(
        message
    )

    bouton_modifier_message = QPushButton("🔒 MODIFIER LE MESSAGE D'ACCUEIL")
    bouton_modifier_message.setToolTip("Modification protégée par le mot de passe administrateur")
    bouton_modifier_message.setStyleSheet(
        "QPushButton { background:#1E3A8A; color:white; font-weight:bold; "
        "padding:9px 16px; border-radius:8px; }"
        "QPushButton:hover { background:#1D4ED8; }"
    )
    bouton_modifier_message.clicked.connect(modifier_message_accueil)
    contenu.addWidget(bouton_modifier_message, alignment=Qt.AlignmentFlag.AlignCenter)
# ============================================================
# PRODUITS
# ============================================================

def _normaliser_recherche_produit(texte):
    import unicodedata
    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(
        c for c in texte
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-zA-Z0-9]+", " ", texte.lower()).strip()


def _produit_correspond_recherche(nom_produit, recherche):
    recherche = _normaliser_recherche_produit(recherche)
    nom = _normaliser_recherche_produit(nom_produit)

    if not recherche:
        return True

    # Début du nom : "coc" -> "Coca Cola"
    if nom.startswith(recherche):
        return True

    mots = nom.split()
    termes = recherche.split()

    # Début de chaque mot : "co co" -> "Coca Cola"
    if len(termes) > 1:
        position = 0
        for terme in termes:
            trouve = False
            while position < len(mots):
                if mots[position].startswith(terme):
                    trouve = True
                    position += 1
                    break
                position += 1
            if not trouve:
                return False
        return True

    # Initiales : "cc" -> "Coca Cola"
    initiales = "".join(mot[0] for mot in mots if mot)
    return initiales.startswith(recherche)


def _normaliser_recherche_produit(texte):
    """Normalise la recherche : accents, casse, espaces et ponctuation."""
    import re
    import unicodedata

    texte = unicodedata.normalize("NFKD", str(texte))
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", " ", texte.lower()).strip()


def _produit_correspond_recherche(nom_produit, recherche):
    """Recherche de type moteur : nom, début de mot et initiales."""
    recherche = _normaliser_recherche_produit(recherche)
    nom = _normaliser_recherche_produit(nom_produit)

    if not recherche:
        return True

    # Exemple : "coc" trouve "Coca Cola".
    if nom.startswith(recherche):
        return True

    mots = nom.split()
    termes = recherche.split()

    # Exemple : "coc col" trouve "Coca Cola".
    if len(termes) > 1:
        position = 0
        for terme in termes:
            trouve = False
            while position < len(mots):
                if mots[position].startswith(terme):
                    trouve = True
                    position += 1
                    break
                position += 1
            if not trouve:
                return False
        return True

    # Exemple : "CC" trouve "Coca Cola".
    initiales = "".join(mot[0] for mot in mots if mot)
    return initiales.startswith(recherche)


def charger_produits(afficher_masques=False):
    if table is None:
        return

    table.setRowCount(0)
    recherche = champ_recherche.text().strip() if champ_recherche else ""

    conn = connexion()
    cur = conn.cursor()

    sql = """
        SELECT id, produit, prix_achat_fc, prix_fc, stock, date_expiration
        FROM produits
        WHERE visible = ?
        ORDER BY id
    """
    params = [0 if afficher_masques else 1]

    cur.execute(sql, params)
    lignes = cur.fetchall()
    conn.close()

    if recherche:
        lignes = [
            ligne for ligne in lignes
            if _produit_correspond_recherche(ligne[1] or "", recherche)
        ]

    for ligne_data in lignes:
        identifiant, produit, prix_achat, prix_fc, stock, expiration = ligne_data
        prix_achat = float(prix_achat or 0)
        prix_fc = float(prix_fc or 0)
        stock = float(stock or 0)

        row = table.rowCount()
        table.insertRow(row)

        valeurs = [
            identifiant,
            produit,
            formater_nombre(prix_achat) + " FC",
            formater_nombre(prix_fc) + " FC",
            f"{calculer_usd(prix_fc):.2f} $",
            formater_nombre(stock),
            calculer_etat(stock),
            expiration or ""
        ]
        ajouter_ligne_tableau(table, row, valeurs)


def ajouter_produit():
    produit = txt_produit.text().strip()

    if not produit:
        QMessageBox.warning(fenetre, "Produit", "Veuillez saisir le nom du produit.")
        return

    # Protection anti-doublon : même produit = même nom logique,
    # indépendamment des majuscules/minuscules et des espaces extérieurs.
    conn = connexion()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, produit FROM produits "
        "WHERE LOWER(TRIM(produit)) = LOWER(TRIM(?))",
        (produit,)
    )
    doublon = cur.fetchone()
    conn.close()

    if doublon is not None:
        QMessageBox.warning(
            fenetre,
            "PRODUIT DÉJÀ EXISTANT",
            f"Le produit « {doublon[1]} » existe déjà.\n\n"
            "Ajout annulé pour éviter un doublon."
        )
        return

    try:
        prix_achat = convertir_nombre(txt_prix_achat_fc.text())
        prix_fc = convertir_nombre(txt_prix_fc.text())
        stock = convertir_nombre(txt_stock.text())
    except ValueError:
        QMessageBox.warning(fenetre, "Erreur", "Vérifiez les valeurs numériques.")
        return

    expiration = txt_expiration.text().strip()

    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO produits
        (produit, prix_achat_fc, prix_fc, stock, date_expiration, visible)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (produit, prix_achat, prix_fc, stock, expiration))
    conn.commit()
    conn.close()

    enregistrer_journal(
        "AJOUT PRODUIT",
        str(produit),
        "Produit ajouté au stock",
        0
    )

    charger_produits()
    vider_champs()

    QMessageBox.information(fenetre, "Produit", "Produit ajouté avec succès.")


def selectionner_produit(row, colonne):
    if table is None:
        return

    try:
        identifiant = table.item(row, 0).text()
        txt_produit.setText(table.item(row, 1).text())

        txt_prix_achat_fc.setText(
            table.item(row, 2).text().replace("FC", "").strip()
        )
        txt_prix_fc.setText(
            table.item(row, 3).text().replace("FC", "").strip()
        )
        txt_prix_usd.setText(table.item(row, 4).text())
        txt_stock.setText(table.item(row, 5).text())
        txt_expiration.setText(table.item(row, 7).text())

        # L'identifiant est conservé dans le champ du tableau.
        _ = identifiant
    except Exception:
        pass


def masquer_tous_les_produits():
    if table is None:
        return

    confirmation = QMessageBox.question(
        fenetre,
        "Masquer les produits",
        "Voulez-vous masquer tous les produits actuellement présents dans la liste ?\n\n"
        "Les produits ne seront pas supprimés.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )

    if confirmation != QMessageBox.StandardButton.Yes:
        return

    conn = connexion()
    cur = conn.cursor()
    cur.execute("UPDATE produits SET visible = 0 WHERE visible = 1")
    conn.commit()
    conn.close()

    enregistrer_journal("MASQUER PRODUITS", "", "Tous les produits ont été masqués.", 0)

    charger_produits()
    vider_champs()


def reafficher_tous_les_produits():
    if table is None:
        return

    confirmation = QMessageBox.question(
        fenetre,
        "Réafficher les produits",
        "Voulez-vous réafficher tous les produits actuellement masqués ?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )

    if confirmation != QMessageBox.StandardButton.Yes:
        return

    conn = connexion()
    cur = conn.cursor()
    cur.execute("UPDATE produits SET visible = 1 WHERE visible = 0")
    conn.commit()
    conn.close()

    enregistrer_journal("RÉAFFICHER PRODUITS", "", "Tous les produits ont été réaffichés.", 0)

    charger_produits()
    vider_champs()


def modifier_produit():
    if table is None:
        return

    ligne = table.currentRow()
    if ligne < 0:
        QMessageBox.warning(fenetre, "Modification", "Sélectionnez un produit.")
        return

    identifiant = table.item(ligne, 0).text()
    produit = txt_produit.text().strip()

    if not produit:
        QMessageBox.warning(fenetre, "Modification", "Le nom du produit est obligatoire.")
        return

    try:
        prix_achat = convertir_nombre(txt_prix_achat_fc.text())
        prix_fc = convertir_nombre(txt_prix_fc.text())
        stock = convertir_nombre(txt_stock.text())
    except ValueError:
        QMessageBox.warning(fenetre, "Erreur", "Vérifiez les valeurs numériques.")
        return

    expiration = txt_expiration.text().strip()

    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        UPDATE produits
        SET produit = ?, prix_achat_fc = ?, prix_fc = ?, stock = ?, date_expiration = ?
        WHERE id = ?
    """, (produit, prix_achat, prix_fc, stock, expiration, identifiant))
    conn.commit()
    conn.close()

    enregistrer_journal(
        "MODIFICATION PRODUIT",
        str(identifiant),
        "Produit modifié : " + produit,
        0
    )

    charger_produits()
    QMessageBox.information(fenetre, "Modification", "Produit modifié avec succès.")


def modifier_quantite():
    if table is None:
        return

    ligne = table.currentRow()
    if ligne < 0:
        QMessageBox.warning(fenetre, "Quantité", "Sélectionnez un produit.")
        return

    identifiant = table.item(ligne, 0).text()

    try:
        quantite = convertir_nombre(txt_stock.text())
    except ValueError:
        QMessageBox.warning(fenetre, "Quantité", "Saisissez une quantité valide.")
        return

    conn = connexion()
    cur = conn.cursor()
    cur.execute("UPDATE produits SET stock = ? WHERE id = ?", (quantite, identifiant))
    conn.commit()
    conn.close()

    enregistrer_journal(
        "MODIFICATION STOCK",
        str(identifiant),
        "Quantité de stock modifiée",
        0
    )

    charger_produits()
    QMessageBox.information(fenetre, "Quantité", "Quantité modifiée avec succès.")


def vider_champs():
    for champ in (
        txt_produit,
        txt_prix_achat_fc,
        txt_prix_fc,
        txt_prix_usd,
        txt_stock,
        txt_expiration,
    ):
        if champ:
            champ.clear()


def mettre_a_jour_usd():
    if txt_prix_fc is None or txt_prix_usd is None:
        return

    try:
        prix_fc = convertir_nombre(txt_prix_fc.text())
        txt_prix_usd.setText(f"{calculer_usd(prix_fc):.2f} $")
    except ValueError:
        txt_prix_usd.clear()


def demander_mot_de_passe():
    mot, ok = QInputDialog.getText(
        fenetre,
        "Administration",
        "Mot de passe administrateur :",
        QLineEdit.EchoMode.Password
    )

    if not ok:
        return False

    if mot != MOT_DE_PASSE_ADMIN:
        QMessageBox.warning(fenetre, "Accès refusé", "Mot de passe incorrect.")
        return False

    return True


def vider_stock():
    if not demander_mot_de_passe():
        return

    confirmation = QMessageBox.question(
        fenetre,
        "VIDER STOCK",
        "ATTENTION !\n\nTous les produits seront supprimés.\n\n"
        "Voulez-vous vraiment continuer ?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )

    if confirmation != QMessageBox.StandardButton.Yes:
        return

    conn = connexion()
    cur = conn.cursor()
    cur.execute("DELETE FROM produits")
    cur.execute("DELETE FROM sqlite_sequence WHERE name = 'produits'")
    conn.commit()
    conn.close()

    enregistrer_journal("VIDER STOCK", "", "Tous les produits ont été supprimés.", 0)

    charger_produits()
    vider_champs()
    QMessageBox.information(fenetre, "VIDER STOCK", "Tous les produits ont été supprimés.")


def supprimer_produit():
    """Suppression définitive du produit sélectionné, avec confirmation."""
    if table is None or table.currentRow() < 0:
        QMessageBox.warning(fenetre, "Suppression", "Sélectionnez d'abord un produit dans la liste.")
        return
    ligne = table.currentRow()
    item_id = table.item(ligne, 0)
    item_nom = table.item(ligne, 1)
    if item_id is None:
        return
    identifiant = int(item_id.text())
    nom = item_nom.text() if item_nom else "ce produit"
    choix = QMessageBox.question(
        fenetre, "Confirmer la suppression définitive",
        f"Supprimer définitivement le produit « {nom} » ?\n\nCette action ne peut pas être annulée.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No
    )
    if choix != QMessageBox.StandardButton.Yes:
        return
    conn = connexion()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM produits WHERE id = ?", (identifiant,))
        if cur.rowcount == 0:
            conn.rollback()
            QMessageBox.warning(fenetre, "Suppression", "Produit introuvable.")
            return
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        QMessageBox.warning(
            fenetre, "Suppression impossible",
            "Ce produit est lié à l'historique des ventes. Pour préserver les factures et les statistiques, il ne peut pas être supprimé physiquement. Vous pouvez le masquer depuis la gestion du stock."
        )
        return
    finally:
        conn.close()
    enregistrer_journal("SUPPRESSION PRODUIT", str(identifiant), f"Produit supprimé : {nom}", 0)
    charger_produits()
    vider_champs()
    QMessageBox.information(fenetre, "Suppression", "Le produit a été supprimé définitivement.")


def afficher_produits():
    global table, champ_recherche, txt_produit, txt_prix_fc
    global txt_prix_usd, txt_prix_achat_fc, txt_stock
    global txt_expiration, titre_mode, bouton_masquer

    nettoyer_zone()

    titre_mode = creer_titre("PRODUITS")
    contenu.addWidget(titre_mode)

    ligne_recherche = QHBoxLayout()
    ligne_recherche.addWidget(QLabel("Recherche :"))

    champ_recherche = QLineEdit()
    champ_recherche.setPlaceholderText("Rechercher un produit… (nom ou initiales)")
    champ_recherche.setClearButtonEnabled(True)
    champ_recherche.setMinimumHeight(36)

    bouton_rechercher = QPushButton("RECHERCHER")
    bouton_rechercher.setMinimumHeight(36)
    bouton_rechercher.setStyleSheet(
        "QPushButton { background:#2563EB; color:white; "
        "border:none; border-radius:7px; padding:6px 16px; font-weight:600; }"
        "QPushButton:hover { background:#1D4ED8; }"
    )
    bouton_rechercher.clicked.connect(charger_produits)
    # Recherche instantanée : le tableau se filtre pendant la saisie.
    champ_recherche.textChanged.connect(charger_produits)

    ligne_recherche.addWidget(champ_recherche)
    ligne_recherche.addWidget(bouton_rechercher)
    contenu.addLayout(ligne_recherche)

    table = QTableWidget()
    table.setColumnCount(8)
    table.setHorizontalHeaderLabels([
        "ID", "PRODUIT", "PRIX ACHAT (FC)", "PRIX VENTE (FC)",
        "PRIX VENTE ($)", "STOCK", "ÉTAT", "EXPIRATION"
    ])
    appliquer_tableau_standard(table)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setStyleSheet("""
        QTableWidget { background: #FFFFFF; alternate-background-color: #F1F5F9; color: #1F2937; }
        QTableWidget::item { background: #FFFFFF; color: #1F2937; padding: 7px; }
        QTableWidget::item:alternate { background: #F1F5F9; color: #1F2937; }
        QTableWidget::item:selected, QTableWidget::item:selected:alternate { background: #1D4ED8; color: #FFFFFF; font-weight: 800; }
    """)
    table.setMinimumHeight(300)
    table.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding
    )
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setDefaultSectionSize(110)
    table.cellClicked.connect(selectionner_produit)
    contenu.addWidget(table)

    bouton_masquer = BoutonMasquerReafficher("MASQUER TOUS LES PRODUITS")
    bouton_masquer.action_simple_clic = masquer_tous_les_produits
    bouton_masquer.action_double_clic = reafficher_tous_les_produits
    contenu.addWidget(bouton_masquer)

    instruction = QLabel(
        "Clic simple : masquer tous les produits\n"
        "Double-clic : réafficher tous les produits"
    )
    instruction.setStyleSheet("font-size: 13px; padding: 4px;")
    contenu.addWidget(instruction)

    grille = QGridLayout()

    grille.addWidget(QLabel("Produit :"), 0, 0)
    txt_produit = QLineEdit()
    grille.addWidget(txt_produit, 0, 1)

    grille.addWidget(QLabel("Prix achat (FC) :"), 0, 2)
    txt_prix_achat_fc = QLineEdit()
    grille.addWidget(txt_prix_achat_fc, 0, 3)

    grille.addWidget(QLabel("Prix vente (FC) :"), 1, 0)
    txt_prix_fc = QLineEdit()
    txt_prix_fc.textChanged.connect(mettre_a_jour_usd)
    grille.addWidget(txt_prix_fc, 1, 1)

    grille.addWidget(QLabel("Prix vente ($) :"), 1, 2)
    txt_prix_usd = QLineEdit()
    txt_prix_usd.setReadOnly(True)
    grille.addWidget(txt_prix_usd, 1, 3)

    grille.addWidget(QLabel("Stock :"), 2, 0)
    txt_stock = QLineEdit()
    grille.addWidget(txt_stock, 2, 1)

    grille.addWidget(QLabel("Expiration :"), 2, 2)
    txt_expiration = QLineEdit()
    grille.addWidget(txt_expiration, 2, 3)

    contenu.addLayout(grille)

    ligne_boutons = QHBoxLayout()
    bouton_ajouter = QPushButton("AJOUTER")
    bouton_modifier = QPushButton("MODIFIER")
    bouton_quantite = QPushButton("MODIFIER QUANTITÉ")
    bouton_vider = QPushButton("VIDER STOCK")
    bouton_supprimer = QPushButton("SUPPRIMER DÉFINITIVEMENT")
    bouton_supprimer.setStyleSheet("background:#B91C1C;color:white;font-weight:bold;padding:7px")

    bouton_ajouter.clicked.connect(ajouter_produit)
    bouton_supprimer.clicked.connect(supprimer_produit)
    bouton_modifier.clicked.connect(modifier_produit)
    bouton_quantite.clicked.connect(modifier_quantite)
    bouton_vider.clicked.connect(vider_stock)

    for bouton in (
        bouton_ajouter,
        bouton_modifier,
        bouton_quantite,
        bouton_supprimer,
        bouton_vider,
    ):
        ligne_boutons.addWidget(bouton)

    contenu.addLayout(ligne_boutons)
    # Navigation clavier cohérente dans le formulaire produit (Tab/Shift+Tab et flèches).
    for champ in (txt_produit, txt_prix_achat_fc, txt_prix_fc, txt_stock, txt_expiration):
        champ.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    fenetre.setTabOrder(txt_produit, txt_prix_achat_fc)
    fenetre.setTabOrder(txt_prix_achat_fc, txt_prix_fc)
    fenetre.setTabOrder(txt_prix_fc, txt_stock)
    fenetre.setTabOrder(txt_stock, txt_expiration)
    fenetre.setTabOrder(txt_expiration, bouton_ajouter)
    fenetre.setTabOrder(bouton_ajouter, bouton_modifier)
    fenetre.setTabOrder(bouton_modifier, bouton_quantite)
    fenetre.setTabOrder(bouton_quantite, bouton_supprimer)
    fenetre.setTabOrder(bouton_supprimer, bouton_vider)
    contenu.addStretch()
    charger_produits()


# ============================================================
# STOCK / ACHATS
# ============================================================

def afficher_stock():
    nettoyer_zone()
    contenu.addWidget(creer_titre("STOCK", 30))

    table_stock = QTableWidget()
    table_stock.setColumnCount(7)
    table_stock.setHorizontalHeaderLabels([
        "ID", "PRODUIT", "PRIX ACHAT (FC)", "PRIX VENTE (FC)",
        "STOCK", "VALEUR PA (FC)", "VALEUR PV (FC)"
    ])
    appliquer_tableau_standard(table_stock)
    table_stock.setMinimumHeight(480)
    table_stock.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding
    )
    table_stock.setAlternatingRowColors(True)
    table_stock.setShowGrid(False)
    table_stock.verticalHeader().setDefaultSectionSize(34)

    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, produit, prix_achat_fc, prix_fc, stock
        FROM produits
        WHERE visible = 1
        ORDER BY id
    """)
    lignes = cur.fetchall()
    conn.close()

    table_stock.setRowCount(len(lignes))
    for row, ligne in enumerate(lignes):
        identifiant, produit, pa, pv, stock = ligne
        pa = float(pa or 0)
        pv = float(pv or 0)
        stock = float(stock or 0)
        ajouter_ligne_tableau(table_stock, row, [
            identifiant,
            produit,
            formater_nombre(pa) + " FC",
            formater_nombre(pv) + " FC",
            formater_nombre(stock),
            formater_nombre(pa * stock) + " FC",
            formater_nombre(pv * stock) + " FC",
        ])

    contenu.addWidget(table_stock)
    contenu.addStretch()


# ============================================================
# ACHATS / RÉQUISITIONS
# ============================================================
# ============================================================
# PDF RÉQUISITION
# ============================================================

def requisition_pdf(requisition_id):
    """Génère un PDF professionnel de la réquisition sur le Bureau Windows."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            Image, KeepTogether
        )
    except ImportError:
        QMessageBox.warning(
            fenetre,
            "PDF",
            "Le module reportlab n'est pas installé.\n\n"
            "Installez-le avec :\n"
            "pip install reportlab"
        )
        return

    conn = connexion()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            numero_requisition,
            date,
            heure,
            total_fc,
            total_usd,
            total_declaration_fc,
            total_general_fc,
            statut
        FROM requisitions
        WHERE id = ?
    """, (requisition_id,))
    requisition = cur.fetchone()

    if requisition is None:
        conn.close()
        QMessageBox.warning(fenetre, "PDF", "Réquisition introuvable.")
        return

    # Le LEFT JOIN conserve toutes les lignes même si aucun transport
    # n'a été enregistré. Les colonnes sont qualifiées pour éviter
    # l'erreur SQLite « ambiguous column name: produit ».
    cur.execute("""
        SELECT
            d.produit,
            d.quantite,
            d.prix_achat_usd,
            d.prix_achat_fc,
            d.total_usd,
            d.total_fc,
            d.declaration_fc_unitaire,
            d.total_declaration_fc,
            d.total_general_fc,
            COALESCE(t.total_transport_fc, 0)
        FROM requisition_details AS d
        LEFT JOIN transport_requisition_details AS t
            ON t.requisition_detail_id = d.id
        WHERE d.requisition_id = ?
        ORDER BY d.id
    """, (requisition_id,))
    details = cur.fetchall()
    conn.close()

    numero = requisition[0]
    date_req = requisition[1]
    heure_req = requisition[2]
    total_fc = float(requisition[3] or 0)
    total_usd = float(requisition[4] or 0)
    total_declaration_fc = float(requisition[5] or 0)
    total_general_fc = float(requisition[6] or (total_fc + total_declaration_fc))
    statut = requisition[7] or "EN ATTENTE"
    total_transport_fc = sum(float(detail[9] or 0) for detail in details)
    transport_present = total_transport_fc > 0
    # Sans transport, les totaux historiques restent inchangés.
    # Avec transport, on ajoute le coût au total de la réquisition.
    if transport_present:
        total_general_fc = total_fc + total_declaration_fc + total_transport_fc

    # Bureau Windows. Fallback sur ~/Desktop si Windows ne renvoie pas le chemin.
    try:
        bureau = Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DesktopLocation
        ))
    except Exception:
        bureau = Path.home() / "Desktop"
    if not bureau.exists():
        bureau = Path.home() / "Desktop"
    bureau.mkdir(parents=True, exist_ok=True)

    nom_fichier = bureau / f"{numero}.pdf"

    largeur, hauteur = landscape(A4)
    doc = SimpleDocTemplate(
        str(nom_fichier),
        pagesize=(largeur, hauteur),
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=13 * mm,
        bottomMargin=16 * mm,
        title=f"Réquisition {numero}",
        author="BILLY-eLBERT STOCK",
        subject="Bon de réquisition d'achats",
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "ReqTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=19, leading=22, textColor=colors.HexColor("#17324D"),
        alignment=TA_LEFT, spaceAfter=2 * mm,
    )
    style_subtitle = ParagraphStyle(
        "ReqSubtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=12, textColor=colors.HexColor("#64748B"),
        alignment=TA_LEFT,
    )
    style_meta = ParagraphStyle(
        "ReqMeta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, leading=12, textColor=colors.HexColor("#334155"),
    )
    style_header = ParagraphStyle(
        "ReqHeader", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7.5, leading=9, textColor=colors.white, alignment=TA_CENTER,
    )
    style_cell = ParagraphStyle(
        "ReqCell", parent=styles["Normal"], fontName="Helvetica",
        fontSize=7.5, leading=9, textColor=colors.HexColor("#1F2937"),
    )
    style_cell_center = ParagraphStyle(
        "ReqCellCenter", parent=style_cell, alignment=TA_CENTER,
    )
    style_cell_right = ParagraphStyle(
        "ReqCellRight", parent=style_cell, alignment=TA_RIGHT,
    )
    style_total_label = ParagraphStyle(
        "ReqTotalLabel", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9, leading=11, textColor=colors.HexColor("#334155"), alignment=TA_RIGHT,
    )
    style_total_value = ParagraphStyle(
        "ReqTotalValue", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=9.5, leading=11, textColor=colors.HexColor("#17324D"), alignment=TA_RIGHT,
    )
    style_grand_label = ParagraphStyle(
        "ReqGrandLabel", parent=style_total_label, fontSize=10.5,
        textColor=colors.white,
    )
    style_grand_value = ParagraphStyle(
        "ReqGrandValue", parent=style_total_value, fontSize=11.5,
        textColor=colors.white,
    )

    story = []

    # En-tête professionnel avec logo si disponible.
    entete_gauche = []
    if LOGO_PATH.exists():
        try:
            logo = Image(str(LOGO_PATH), width=17 * mm, height=17 * mm)
            logo.hAlign = "LEFT"
            entete_gauche.append(logo)
        except Exception:
            pass
    entete_gauche.append(Paragraph(__import__("xml.sax.saxutils", fromlist=["escape"]).escape(obtenir_message_accueil_pdf()), style_title))
    entete_gauche.append(Paragraph("BON DE RÉQUISITION D'ACHATS", style_subtitle))

    info = [
        [Paragraph("N° RÉQUISITION", style_meta), Paragraph(str(numero), style_meta)],
        [Paragraph("DATE / HEURE", style_meta), Paragraph(f"{date_req} — {heure_req}", style_meta)],
        [Paragraph("STATUT", style_meta), Paragraph(str(statut), style_meta)],
    ]
    info_table = Table(info, colWidths=[34 * mm, 52 * mm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    head = Table([[entete_gauche, info_table]], colWidths=[174 * mm, 86 * mm])
    head.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("LINEBELOW", (0, 0), (-1, 0), 4, colors.HexColor("#2563EB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([head, Spacer(1, 7 * mm)])

    # Tableau des lignes de la réquisition.
    # Sans transport, le tableau garde strictement les colonnes d'origine.
    # Si un transport est enregistré, sa colonne remplace TOTAL MARCHANDISE FC.
    headers = [
        "PRODUIT", "QTÉ", "PU $", "PU FC", "TOTAL $",
        "DÉCL./UNITÉ FC", "TOTAL DÉCL. FC",
        "TRANSPORT FC" if transport_present else "TOTAL MARCHANDISE FC",
        "TOTAL LIGNE FC"
    ]
    data = [[Paragraph(h, style_header) for h in headers]]
    for detail in details:
        produit, quantite, pu_usd, pu_fc, pt_usd, pt_fc, decl_u, total_decl, total_ligne_orig, transport_ligne = detail
        pt_fc = float(pt_fc or 0)
        total_decl = float(total_decl or 0)
        transport_ligne = float(transport_ligne or 0)
        if transport_present:
            total_ligne = pt_fc + total_decl + transport_ligne
            valeur_colonne = transport_ligne
        else:
            total_ligne = float(total_ligne_orig or (pt_fc + total_decl))
            valeur_colonne = pt_fc
        data.append([
            Paragraph(str(produit), style_cell),
            Paragraph(formater_nombre(quantite), style_cell_center),
            Paragraph(f"{float(pu_usd or 0):,.2f} $".replace(",", " "), style_cell_right),
            Paragraph(formater_nombre(pu_fc) + " FC", style_cell_right),
            Paragraph(f"{float(pt_usd or 0):,.2f} $".replace(",", " "), style_cell_right),
            Paragraph(formater_nombre(decl_u) + " FC", style_cell_right),
            Paragraph(formater_nombre(total_decl) + " FC", style_cell_right),
            Paragraph(formater_nombre(valeur_colonne) + " FC", style_cell_right),
            Paragraph(formater_nombre(total_ligne) + " FC", style_cell_right),
        ])

    col_widths = [47 * mm, 15 * mm, 21 * mm, 26 * mm, 24 * mm, 29 * mm, 30 * mm, 34 * mm, 34 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243B53")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for row in range(1, len(data)):
        if row % 2 == 0:
            table_style.append(("BACKGROUND", (0, row), (-1, row), colors.HexColor("#F8FAFC")))
        else:
            table_style.append(("BACKGROUND", (0, row), (-1, row), colors.white))
    table.setStyle(TableStyle(table_style))
    story.append(table)
    story.append(Spacer(1, 7 * mm))

    # Bloc de synthèse.
    lignes_synthese = [
        [Paragraph("TOTAL MARCHANDISES", style_total_label), Paragraph(formater_nombre(total_fc) + " FC", style_total_value)],
        [Paragraph("TOTAL FRAIS DE DÉCLARATION", style_total_label), Paragraph(formater_nombre(total_declaration_fc) + " FC", style_total_value)],
    ]
    if transport_present:
        lignes_synthese.append([
            Paragraph("TOTAL TRANSPORT", style_total_label),
            Paragraph(formater_nombre(total_transport_fc) + " FC", style_total_value),
        ])
    lignes_synthese.extend([
        [Paragraph("TOTAL RÉQUISITION FC" if transport_present else "TOTAL RÉQUISITION", style_grand_label), Paragraph(formater_nombre(total_general_fc) + " FC", style_grand_value)],
        [Paragraph("NET À PAYER EN DOLLARS", style_total_label), Paragraph(f"{total_usd:,.2f} $".replace(",", " "), style_total_value)],
    ])
    index_total = 3 if transport_present else 2
    index_usd = index_total + 1
    synthese = Table(lignes_synthese, colWidths=[65 * mm, 48 * mm], hAlign="RIGHT")
    synthese.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, index_total - 1), colors.HexColor("#F8FAFC")),
        ("BACKGROUND", (0, index_total), (-1, index_total), colors.HexColor("#1D4ED8")),
        ("BACKGROUND", (0, index_usd), (-1, index_usd), colors.HexColor("#EFF6FF")),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#E2E8F0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(synthese)
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "Document généré automatiquement par " + __import__("xml.sax.saxutils", fromlist=["escape"]).escape(obtenir_message_accueil_pdf()) + " — réquisition enregistrée dans la base de données.",
        ParagraphStyle("FooterNote", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5,
                        textColor=colors.HexColor("#64748B"), alignment=TA_LEFT)
    ))

    def footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas_obj.line(14 * mm, 11 * mm, largeur - 14 * mm, 11 * mm)
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.setFillColor(colors.HexColor("#64748B"))
        canvas_obj.drawString(14 * mm, 6.5 * mm, f"{obtenir_message_accueil_pdf()} — {numero}")
        canvas_obj.drawRightString(largeur - 14 * mm, 6.5 * mm, f"Page {doc_obj.page}")
        canvas_obj.restoreState()

    try:
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
    except Exception as erreur:
        QMessageBox.critical(
            fenetre,
            "PDF",
            "La création du PDF a échoué :\n\n" + str(erreur)
        )
        return

    QMessageBox.information(
        fenetre,
        "PDF",
        "Réquisition PDF créée avec succès.\n\n"
        f"Fichier : {nom_fichier.name}\n"
        f"Emplacement : {nom_fichier.parent}"
    )


def coloriser_onglets_achats(onglets):
    """Applique le même principe de jeu de couleurs que les onglets Ventes."""
    pages = [
        (onglets.widget(0), "#FFF7ED", "#EA580C"),
        (onglets.widget(1), "#F0FDF4", "#16A34A"),
        (onglets.widget(2), "#FAF5FF", "#7C3AED"),
        (onglets.widget(3), "#EFF6FF", "#2563EB"),
        (onglets.widget(4), "#FEF2F2", "#DC2626"),
    ]

    for index, (page, fond, texte) in enumerate(pages):
        if page is not None:
            page.setStyleSheet(
                f"QWidget {{ background-color: {fond}; }}"
            )
        onglets.tabBar().setTabTextColor(index, texte)

    onglets.setStyleSheet("""
        QTabBar::tab {
            padding: 10px 16px;
            font-weight: bold;
            border: 1px solid #CBD5E1;
            border-bottom: none;
            background: #E2E8F0;
        }
        QTabBar::tab:selected {
            background: #FFFFFF;
        }
        QTabWidget::pane {
            border: 1px solid #CBD5E1;
        }
    """)


def afficher_achats():

    global table_requisition
    global table_produits_requisition
    global spin_quantite_requisition
    global champ_prix_usd_requisition
    global champ_prix_fc_requisition
    global champ_declaration_requisition
    global label_total_requisition_usd
    global label_total_requisition_fc
    global label_total_declaration_requisition_fc
    global label_total_general_requisition_fc

    nettoyer_zone()

    contenu.addWidget(
        creer_titre("ACHATS", 30)
    )

    # ========================================================
    # ONGLETS
    # ========================================================

    onglets_achats = QTabWidget()

    page_requisition = QWidget()
    page_historique_requisition = QWidget()
    page_dashboard_achats = QWidget()
    page_meilleure_requisition = QWidget()
    page_requisition_faible = QWidget()

    onglets_achats.addTab(
        page_requisition,
        "RÉQUISITION"
    )

    onglets_achats.addTab(
        page_historique_requisition,
        "HISTORIQUE RÉQUISITIONS"
    )

    onglets_achats.addTab(
        page_dashboard_achats,
        "DASHBOARD"
    )
    onglets_achats.addTab(
        page_meilleure_requisition,
        "MEILLEURE RÉQUISITION"
    )
    onglets_achats.addTab(
        page_requisition_faible,
        "RÉQUISITION TROP FAIBLE"
    )

    contenu.addWidget(
        onglets_achats
    )
    coloriser_onglets_achats(onglets_achats)

    # ========================================================
    # PANIER TEMPORAIRE
    # ========================================================

    panier_requisition = []

    # ========================================================
    # BROUILLON AUTOMATIQUE DE RÉQUISITION
    # ========================================================
    fichier_brouillon_requisition = BROUILLONS_DIR / "requisition_en_cours.json"

    def sauvegarder_brouillon_requisition(*args):
        try:
            saisie = {
                "prix_usd": champ_prix_usd_requisition.text().strip(),
                "declaration_fc": champ_declaration_requisition.text().strip(),
                "quantite": spin_quantite_requisition.value(),
            }
            a_saisie = bool(saisie["prix_usd"]) or (
                saisie["declaration_fc"] not in ("", "0", "0.0", "0,0")
            ) or float(saisie["quantite"] or 0) != 1
            if panier_requisition or a_saisie:
                donnees = {
                    "version": 1,
                    "mis_a_jour": datetime.now().isoformat(timespec="seconds"),
                    "articles": panier_requisition,
                    "saisie": saisie,
                }
                temporaire = fichier_brouillon_requisition.with_suffix(".tmp")
                temporaire.write_text(
                    json.dumps(donnees, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporaire.replace(fichier_brouillon_requisition)
            elif fichier_brouillon_requisition.exists():
                fichier_brouillon_requisition.unlink()
        except Exception as erreur:
            print("Sauvegarde du brouillon impossible :", erreur)

    def charger_brouillon_requisition():
        if not fichier_brouillon_requisition.exists():
            return False
        try:
            donnees = json.loads(fichier_brouillon_requisition.read_text(encoding="utf-8"))
            panier_requisition.clear()
            for a in donnees.get("articles", []):
                if not isinstance(a, dict) or "produit" not in a:
                    continue
                q = float(a.get("quantite", 0) or 0)
                pu_usd = float(a.get("prix_usd", 0) or 0)
                pu_fc = float(a.get("prix_fc", 0) or 0)
                decl = float(a.get("declaration_fc_unitaire", 0) or 0)
                total_usd = float(a.get("total_usd", q * pu_usd) or 0)
                total_fc = float(a.get("total_fc", q * pu_fc) or 0)
                total_decl = float(a.get("total_declaration_fc", q * decl) or 0)
                panier_requisition.append({
                    "id": int(a.get("id", 0) or 0),
                    "produit": str(a.get("produit", "")),
                    "quantite": q, "prix_usd": pu_usd, "prix_fc": pu_fc,
                    "total_usd": total_usd, "total_fc": total_fc,
                    "declaration_fc_unitaire": decl,
                    "total_declaration_fc": total_decl,
                    "total_general_fc": float(a.get("total_general_fc", total_fc + total_decl) or (total_fc + total_decl)),
                })
            return bool(panier_requisition) or bool(donnees.get("saisie"))
        except Exception as erreur:
            print("Restauration du brouillon impossible :", erreur)
            return False

    # ========================================================
    # PAGE RÉQUISITION
    # ========================================================

    layout_req = QVBoxLayout(
        page_requisition
    )

    # ========================================================
    # RECHERCHE
    # ========================================================

    ligne_recherche = QHBoxLayout()

    ligne_recherche.addWidget(
        QLabel("Recherche :")
    )

    champ_recherche_req = QLineEdit()

    champ_recherche_req.setPlaceholderText(
        "Rechercher un produit..."
    )

    bouton_rechercher_req = QPushButton(
        "RECHERCHER"
    )

    ligne_recherche.addWidget(
        champ_recherche_req
    )

    ligne_recherche.addWidget(
        bouton_rechercher_req
    )

    layout_req.addLayout(
        ligne_recherche
    )

    # ========================================================
    # PRODUITS EN RUPTURE / STOCK FAIBLE
    # ========================================================

    layout_req.addWidget(
        QLabel(
            "PRODUITS À RÉAPPROVISIONNER"
        )
    )

    table_produits_requisition = QTableWidget()

    table_produits_requisition.setColumnCount(6)

    table_produits_requisition.setHorizontalHeaderLabels([
        "ID",
        "PRODUIT",
        "STOCK",
        "ÉTAT",
        "PRIX ACHAT (FC)",
        "PRIX ACHAT ($)"
    ])

    appliquer_tableau_standard(
        table_produits_requisition
    )
    table_produits_requisition.setAlternatingRowColors(True)
    table_produits_requisition.setShowGrid(False)
    table_produits_requisition.setStyleSheet("""
        QTableWidget { background: #FFFFFF; alternate-background-color: #F1F5F9; color: #1F2937; }
        QTableWidget::item { background: #FFFFFF; color: #1F2937; padding: 7px; }
        QTableWidget::item:alternate { background: #F1F5F9; color: #1F2937; }
        QTableWidget::item:selected, QTableWidget::item:selected:alternate { background: #1D4ED8; color: #FFFFFF; font-weight: 800; }
    """)

    layout_req.addWidget(
        table_produits_requisition
    )

    # ========================================================
    # SAISIE
    # ========================================================

    ligne_saisie = QHBoxLayout()

    ligne_saisie.addWidget(
        QLabel("Quantité :")
    )

    spin_quantite_requisition = QDoubleSpinBox()

    spin_quantite_requisition.setMinimum(
        0.01
    )

    spin_quantite_requisition.setMaximum(
        999999999
    )

    spin_quantite_requisition.setDecimals(
        2
    )

    spin_quantite_requisition.setValue(
        1
    )

    ligne_saisie.addWidget(
        spin_quantite_requisition
    )

    ligne_saisie.addWidget(
        QLabel("PU $ :")
    )

    champ_prix_usd_requisition = QLineEdit()

    champ_prix_usd_requisition.setPlaceholderText(
        "Prix achat en dollars"
    )

    ligne_saisie.addWidget(
        champ_prix_usd_requisition
    )

    ligne_saisie.addWidget(
        QLabel("PU FC :")
    )

    champ_prix_fc_requisition = QLineEdit()

    champ_prix_fc_requisition.setReadOnly(
        True
    )

    champ_prix_fc_requisition.setPlaceholderText(
        "Conversion automatique"
    )

    ligne_saisie.addWidget(
        champ_prix_fc_requisition
    )

    # --------------------------------------------------------
    # FRAIS DE DÉCLARATION
    # --------------------------------------------------------
    ligne_saisie.addWidget(
        QLabel("Déclaration / unité (FC) :")
    )

    champ_declaration_requisition = QLineEdit()
    champ_declaration_requisition.setPlaceholderText(
        "Ex. 1500 par sac"
    )
    champ_declaration_requisition.setText("0")
    ligne_saisie.addWidget(
        champ_declaration_requisition
    )

    layout_req.addLayout(
        ligne_saisie
    )

    bouton_calculatrice_req = QPushButton("🧮 CALCULATRICE PU / TOTAL")
    bouton_calculatrice_req.setToolTip("Calculer le prix unitaire en divisant le montant total par la quantité")
    layout_req.addWidget(bouton_calculatrice_req)

    def ouvrir_calculatrice_requisition():
        dlg = QDialog(fenetre)
        dlg.setWindowTitle("Calculatrice de réquisition — PU et total")
        dlg.resize(420, 260)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("QUANTITÉ COMMANDÉE"))
        qte = QDoubleSpinBox(); qte.setRange(0.0001, 999999999); qte.setDecimals(4); qte.setValue(max(0.01, spin_quantite_requisition.value()))
        lay.addWidget(qte)
        lay.addWidget(QLabel("MONTANT TOTAL ($)"))
        montant = QLineEdit(); montant.setPlaceholderText("Ex. 125.00"); lay.addWidget(montant)
        resultat = QLabel("PU : —    |    Total : —")
        resultat.setStyleSheet("font-size:16px;font-weight:bold;padding:10px;color:#0F766E")
        lay.addWidget(resultat)
        def calculer_pu():
            try:
                total = float(montant.text().strip().replace(" ", "").replace(",", "."))
                if total < 0 or qte.value() <= 0: raise ValueError
                pu = total / qte.value()
                resultat.setText(f"PU : {pu:,.2f} $    |    Total : {total:,.2f} $")
                champ_prix_usd_requisition.setText(f"{pu:.2f}")
                spin_quantite_requisition.setValue(qte.value())
            except Exception:
                QMessageBox.warning(dlg, "Calcul impossible", "Saisissez une quantité positive et un montant total valide.")
        btn = QPushButton("CALCULER ET REPORTER LE PU"); btn.clicked.connect(calculer_pu); lay.addWidget(btn)
        fermer = QPushButton("Fermer"); fermer.clicked.connect(dlg.accept); lay.addWidget(fermer)
        dlg.exec()
    bouton_calculatrice_req.clicked.connect(ouvrir_calculatrice_requisition)

    # ========================================================
    # BOUTONS
    # ========================================================
    ligne_actions = QHBoxLayout()

    bouton_ajouter_req = QPushButton(
        "AJOUTER À LA RÉQUISITION"
    )

    bouton_ajout_manuel = QPushButton(
        "AJOUTER PRODUIT MANUELLEMENT"
    )

    bouton_modifier_req = QPushButton(
        "MODIFIER"
    )

    bouton_supprimer_req = QPushButton(
        "SUPPRIMER"
    )

    bouton_vider_req = QPushButton(
        "VIDER"
    )

    ligne_actions.addWidget(
        bouton_ajouter_req
    )

    ligne_actions.addWidget(
        bouton_ajout_manuel
    )

    ligne_actions.addWidget(
        bouton_modifier_req
    )

    ligne_actions.addWidget(
        bouton_supprimer_req
    )

    ligne_actions.addWidget(
        bouton_vider_req
    )

    layout_req.addLayout(
        ligne_actions
    )

    # ========================================================
    # TABLEAU RÉQUISITION
    # ========================================================

    layout_req.addWidget(
        QLabel(
            "CONTENU DE LA RÉQUISITION"
        )
    )

    table_requisition = QTableWidget()

    table_requisition.setColumnCount(10)

    table_requisition.setHorizontalHeaderLabels([
        "N°",
        "PRODUIT",
        "QTÉ",
        "PU $",
        "PU FC",
        "TOTAL $",
        "TOTAL FC",
        "DÉCL. / UNITÉ FC",
        "TOTAL DÉCL. FC",
        "TOTAL MARCHANDISE FC"
    ])

    appliquer_tableau_standard(
        table_requisition
    )

    layout_req.addWidget(
        table_requisition
    )

    # ========================================================
    # TOTAUX
    # ========================================================

    ligne_totaux_req = QHBoxLayout()

    label_total_requisition_usd = QLabel(
        "NET À PAYER : 0.00 $"
    )

    label_total_requisition_fc = QLabel(
        "0 FC"
    )

    label_total_declaration_requisition_fc = QLabel(
        "DÉCLARATIONS : 0 FC"
    )

    label_total_general_requisition_fc = QLabel(
        "TOTAL RÉQUISITION : 0 FC"
    )

    label_total_requisition_usd.setStyleSheet(
        """
        font-size: 18px;
        font-weight: bold;
        padding: 8px;
        """
    )

    label_total_requisition_fc.setStyleSheet(
        """
        font-size: 18px;
        font-weight: bold;
        padding: 8px;
        """
    )

    ligne_totaux_req.addWidget(
        label_total_requisition_usd
    )

    ligne_totaux_req.addWidget(
        label_total_requisition_fc
    )

    ligne_totaux_req.addWidget(
        label_total_declaration_requisition_fc
    )

    ligne_totaux_req.addWidget(
        label_total_general_requisition_fc
    )

    ligne_totaux_req.addStretch()

    bouton_enregistrer_req = QPushButton(
        "ENREGISTRER LA RÉQUISITION"
    )

    bouton_pdf_req = QPushButton(
        "PDF"
    )

    ligne_totaux_req.addWidget(
        bouton_enregistrer_req
    )

    ligne_totaux_req.addWidget(
        bouton_pdf_req
    )

    layout_req.addLayout(
        ligne_totaux_req
    )

    # ========================================================
    # CONVERSION $ -> FC
    # ========================================================

    def convertir_prix_requisition():

        texte = (
            champ_prix_usd_requisition
            .text()
            .strip()
        )

        if not texte:

            champ_prix_fc_requisition.clear()

            return

        try:

            prix_usd = convertir_nombre(
                texte
            )

            taux = obtenir_taux()

            if taux <= 0:

                champ_prix_fc_requisition.clear()

                return

            prix_fc = (
                prix_usd * taux
            )

            champ_prix_fc_requisition.setText(
                formater_nombre(prix_fc)
            )

        except Exception:

            champ_prix_fc_requisition.clear()

    champ_prix_usd_requisition.textChanged.connect(
        convertir_prix_requisition
    )

    # ========================================================
    # CHARGER PRODUITS À RÉAPPROVISIONNER
    # ========================================================

    def charger_produits_requisition():

        recherche = (
            champ_recherche_req
            .text()
            .strip()
        )

        conn = connexion()

        try:

            cur = conn.cursor()
            sql = """
                SELECT
                    id,
                    produit,
                    stock,
                    prix_achat_fc
                FROM produits
                WHERE visible = 1
                  AND stock < 10
            """

            params = []

            if recherche:

                sql += """
                    AND produit LIKE ?
                """

                params.append(
                    "%" + recherche + "%"
                )

            sql += """
                ORDER BY stock ASC, id ASC
            """

            cur.execute(
                sql,
                params
            )

            produits = cur.fetchall()

        finally:

            conn.close()

        table_produits_requisition.clearContents()

        table_produits_requisition.setRowCount(
            len(produits)
        )

        taux = obtenir_taux()

        for row, produit in enumerate(
            produits
        ):

            produit_id = produit[0]

            nom = (
                produit[1]
                or ""
            )

            stock = float(
                produit[2] or 0
            )

            prix_fc = float(
                produit[3] or 0
            )

            prix_usd = (
                prix_fc / taux
                if taux > 0
                else 0
            )

            ajouter_ligne_tableau(
                table_produits_requisition,
                row,
                [
                    produit_id,
                    nom,
                    formater_nombre(stock),
                    calculer_etat(stock),
                    formater_nombre(
                        prix_fc
                    ) + " FC",
                    f"{prix_usd:.2f} $"
                ]
            )

    # ========================================================
    # ACTUALISER LE PANIER
    # ========================================================

    def actualiser_table_requisition():

        table_requisition.clearContents()

        table_requisition.setRowCount(
            len(panier_requisition)
        )

        total_usd = 0
        total_fc = 0
        total_declaration_fc = 0

        for row, article in enumerate(
            panier_requisition
        ):

            total_usd += float(
                article["total_usd"]
            )

            total_fc += float(
                article["total_fc"]
            )

            total_declaration_fc += float(
                article.get("total_declaration_fc", 0)
            )

            total_general_article_fc = (
                float(article["total_fc"])
                + float(article.get("total_declaration_fc", 0))
            )

            ajouter_ligne_tableau(
                table_requisition,
                row,
                [
                    row + 1,
                    article["produit"],
                    formater_nombre(
                        article["quantite"]
                    ),
                    f'{article["prix_usd"]:.2f} $',
                    formater_nombre(
                        article["prix_fc"]
                    ) + " FC",
                    f'{article["total_usd"]:.2f} $',
                    formater_nombre(
                        article["total_fc"]
                    ) + " FC",
                    formater_nombre(
                        article.get("declaration_fc_unitaire", 0)
                    ) + " FC",
                    formater_nombre(
                        article.get("total_declaration_fc", 0)
                    ) + " FC",
                    formater_nombre(
                        total_general_article_fc
                    ) + " FC"
                ]
            )

        total_general_fc = total_fc + total_declaration_fc

        label_total_requisition_usd.setText(
            "NET À PAYER : "
            + f"{total_usd:,.2f}".replace(",", " ")
            + " $"
        )

        label_total_requisition_fc.setText(
            "MARCHANDISES : "
            + formater_nombre(
                total_fc
            )
            + " FC"
        )

        label_total_declaration_requisition_fc.setText(
            "DÉCLARATIONS : "
            + formater_nombre(
                total_declaration_fc
            )
            + " FC"
        )

        label_total_general_requisition_fc.setText(
            "TOTAL RÉQUISITION : "
            + formater_nombre(
                total_general_fc
            )
            + " FC"
        )

    # ========================================================
    # AJOUTER PRODUIT DEPUIS LA LISTE
        sauvegarder_brouillon_requisition()

    # ========================================================

    def ajouter_produit_requisition():

        row = (
            table_produits_requisition
            .currentRow()
        )

        if row < 0:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Sélectionnez d'abord un produit."
            )

            return

        item_id = (
            table_produits_requisition
            .item(row, 0)
        )

        item_nom = (
            table_produits_requisition
            .item(row, 1)
        )
        if item_id is None or item_nom is None:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Produit invalide."
            )

            return

        try:

            produit_id = int(
                item_id.text()
            )

        except Exception:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "ID du produit invalide."
            )

            return

        produit_nom = item_nom.text().strip()

        quantite = float(
            spin_quantite_requisition.value()
        )

        if quantite <= 0:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "La quantité doit être supérieure à zéro."
            )

            return

        texte_prix = (
            champ_prix_usd_requisition
            .text()
            .strip()
        )

        if not texte_prix:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Veuillez saisir le prix d'achat unitaire."
            )

            champ_prix_usd_requisition.setFocus()

            return

        try:

            prix_usd = convertir_nombre(
                texte_prix
            )

        except Exception:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Prix d'achat invalide."
            )

            return

        if prix_usd <= 0:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Le prix d'achat doit être supérieur à zéro."
            )

            return

        taux = obtenir_taux()

        if taux <= 0:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Le taux de change est invalide."
            )

            return

        prix_fc = (
            prix_usd * taux
        )

        texte_declaration = (
            champ_declaration_requisition
            .text()
            .strip()
        )
        try:
            declaration_fc_unitaire = (
                convertir_nombre(texte_declaration)
                if texte_declaration
                else 0
            )
        except Exception:
            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Frais de déclaration invalide."
            )
            champ_declaration_requisition.setFocus()
            return

        if declaration_fc_unitaire < 0:
            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Les frais de déclaration ne peuvent pas être négatifs."
            )
            return

        total_declaration_fc = (
            quantite * declaration_fc_unitaire
        )

        # ----------------------------------------------------
        # PRODUIT EXISTANT
        # ----------------------------------------------------

        for article in panier_requisition:

            if article["id"] == produit_id:

                article["quantite"] += quantite

                article["prix_usd"] = (
                    prix_usd
                )

                article["prix_fc"] = (
                    prix_fc
                )

                article["total_usd"] = (
                    article["quantite"]
                    * prix_usd
                )

                article["total_fc"] = (
                    article["quantite"]
                    * prix_fc
                )

                article["declaration_fc_unitaire"] = (
                    declaration_fc_unitaire
                )

                article["total_declaration_fc"] = (
                    article["quantite"]
                    * declaration_fc_unitaire
                )

                article["total_general_fc"] = (
                    article["total_fc"]
                    + article["total_declaration_fc"]
                )

                actualiser_table_requisition()

                champ_prix_usd_requisition.clear()
                champ_declaration_requisition.setText("0")

                spin_quantite_requisition.setValue(
                    1
                )

                return

        # ----------------------------------------------------
        # NOUVEAU PRODUIT
        # ----------------------------------------------------

        panier_requisition.append({
            "id": produit_id,
            "produit": produit_nom,
            "quantite": quantite,
            "prix_usd": prix_usd,
            "prix_fc": prix_fc,
            "total_usd": (
                quantite * prix_usd
            ),
            "total_fc": (
                quantite * prix_fc
            ),
            "declaration_fc_unitaire": declaration_fc_unitaire,
            "total_declaration_fc": total_declaration_fc,
            "total_general_fc": (
                quantite * prix_fc
                + total_declaration_fc
            )
        })

        actualiser_table_requisition()

        champ_prix_usd_requisition.clear()
        champ_declaration_requisition.setText("0")

        spin_quantite_requisition.setValue(
            1
        )

    # ========================================================
    # AJOUTER PRODUIT MANUELLEMENT
    # ========================================================

    def ajouter_produit_manuellement():

        conn = connexion()

        try:

            cur = conn.cursor()
            cur.execute("""
                SELECT
                    id,
                    produit,
                    prix_achat_fc
                FROM produits
                WHERE visible = 1
                ORDER BY produit
            """)

            produits = cur.fetchall()

        finally:

            conn.close()

        if not produits:

            QMessageBox.warning(
                fenetre,
                "PRODUITS",
                "Aucun produit disponible."
            )

            return

        noms = [
            str(produit[1])
            for produit in produits
        ]

        nom, ok = QInputDialog.getItem(
            fenetre,
            "AJOUTER PRODUIT MANUELLEMENT",
            "Sélectionnez le produit :",
            noms,
            0,
            False
        )

        if not ok:

            return

        produit_selectionne = None

        for produit in produits:

            if str(produit[1]) == nom:

                produit_selectionne = produit

                break

        if produit_selectionne is None:

            return

        produit_id = (
            produit_selectionne[0]
        )

        prix_fc_base = float(
            produit_selectionne[2] or 0
        )

        taux = obtenir_taux()

        if taux <= 0:

            QMessageBox.warning(
                fenetre,
                "TAUX",
                "Le taux de change est invalide."
            )

            return

        # ----------------------------------------------------
        # QUANTITÉ
        # ----------------------------------------------------

        quantite, ok = QInputDialog.getDouble(
            fenetre,
            "QUANTITÉ",
            "Quantité :",
            1,
            0.01,
            1000000,
            2
        )

        if not ok:

            return

        if quantite <= 0:

            return

        # ----------------------------------------------------
        # PRIX D'ACHAT MANUEL
        # ----------------------------------------------------

        prix_usd, ok = QInputDialog.getDouble(
            fenetre,
            "PRIX D'ACHAT",
            "Prix d'achat unitaire ($) :",
            (
                prix_fc_base / taux
                if prix_fc_base > 0
                else 0
            ),
            0.01,
            999999999,
            2
        )

        if not ok:

            return

        if prix_usd <= 0:

            return

        prix_fc = (
            prix_usd * taux
        )

        declaration_fc_unitaire, ok = QInputDialog.getDouble(
            fenetre,
            "FRAIS DE DÉCLARATION",
            "Déclaration par unité (FC) :",
            0,
            0,
            999999999,
            2
        )

        if not ok:
            return

        # ----------------------------------------------------
        # SI LE PRODUIT EXISTE DÉJÀ
        # ----------------------------------------------------

        for article in panier_requisition:

            if article["id"] == produit_id:

                article["quantite"] += (
                    quantite
                )

                article["prix_usd"] = (
                    prix_usd
                )

                article["prix_fc"] = (
                    prix_fc
                )

                article["total_usd"] = (
                    article["quantite"]
                    * prix_usd
                )

                article["total_fc"] = (
                    article["quantite"]
                    * prix_fc
                )

                article["declaration_fc_unitaire"] = (
                    declaration_fc_unitaire
                )
                article["total_declaration_fc"] = (
                    article["quantite"]
                    * declaration_fc_unitaire
                )
                article["total_general_fc"] = (
                    article["total_fc"]
                    + article["total_declaration_fc"]
                )

                actualiser_table_requisition()

                return

        # ----------------------------------------------------
        # NOUVEAU PRODUIT
        # ----------------------------------------------------

        panier_requisition.append({
            "id": produit_id,
            "produit": nom,
            "quantite": quantite,
            "prix_usd": prix_usd,
            "prix_fc": prix_fc,
            "total_usd": (
                quantite * prix_usd
            ),
            "total_fc": (
                quantite * prix_fc
            ),
            "declaration_fc_unitaire": declaration_fc_unitaire,
            "total_declaration_fc": (
                quantite * declaration_fc_unitaire
            ),
            "total_general_fc": (
                quantite * prix_fc
                + quantite * declaration_fc_unitaire
            )
        })

        actualiser_table_requisition()

    # ========================================================
    # MODIFIER
    # ========================================================
    def modifier_produit_requisition():

        row = (
            table_requisition
            .currentRow()
        )

        if row < 0:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Sélectionnez une ligne à modifier."
            )

            return

        article = panier_requisition[row]

        quantite, ok = QInputDialog.getDouble(
            fenetre,
            "MODIFIER QUANTITÉ",
            "Nouvelle quantité :",
            float(
                article["quantite"]
            ),
            0.01,
            999999999,
            2
        )

        if not ok:

            return

        prix_usd, ok = QInputDialog.getDouble(
            fenetre,
            "MODIFIER PRIX",
            "Nouveau prix d'achat ($) :",
            float(
                article["prix_usd"]
            ),
            0.01,
            999999999,
            2
        )

        if not ok:

            return

        declaration_fc_unitaire, ok = QInputDialog.getDouble(
            fenetre,
            "MODIFIER DÉCLARATION",
            "Frais de déclaration par unité (FC) :",
            float(article.get("declaration_fc_unitaire", 0)),
            0,
            999999999,
            2
        )

        if not ok:
            return

        taux = obtenir_taux()

        if taux <= 0:

            QMessageBox.warning(
                fenetre,
                "TAUX",
                "Le taux de change est invalide."
            )

            return

        article["quantite"] = quantite

        article["prix_usd"] = prix_usd

        article["prix_fc"] = (
            prix_usd * taux
        )

        article["total_usd"] = (
            quantite * prix_usd
        )

        article["total_fc"] = (
            quantite
            * article["prix_fc"]
        )

        article["declaration_fc_unitaire"] = (
            declaration_fc_unitaire
        )
        article["total_declaration_fc"] = (
            quantite * declaration_fc_unitaire
        )
        article["total_general_fc"] = (
            article["total_fc"]
            + article["total_declaration_fc"]
        )

        actualiser_table_requisition()

    # ========================================================
    # SUPPRIMER
    # ========================================================

    def supprimer_produit_requisition():

        row = (
            table_requisition
            .currentRow()
        )

        if row < 0:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Sélectionnez une ligne à supprimer."
            )

            return

        produit = (
            panier_requisition[row]
            ["produit"]
        )

        confirmation = QMessageBox.question(
            fenetre,
            "SUPPRESSION",
            'Supprimer "' + produit + '" ?',
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if confirmation != QMessageBox.StandardButton.Yes:

            return

        panier_requisition.pop(
            row
        )

        actualiser_table_requisition()

    # ========================================================
    # VIDER
    # ========================================================

    def vider_requisition():

        if not panier_requisition:

            return

        confirmation = QMessageBox.question(
            fenetre,
            "VIDER",
            "Voulez-vous vider toute la réquisition ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if confirmation != QMessageBox.StandardButton.Yes:

            return

        panier_requisition.clear()

        actualiser_table_requisition()

    # ========================================================
    # TRANSPORT PAR MARCHANDISE (APRÈS RÉQUISITION)
    # ========================================================

    def ouvrir_calcul_transport_requisition(requisition_id, numero_req):
        """Saisit le coût de transport par unité pour chaque marchandise."""
        conn = connexion()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT d.id, d.produit, d.quantite,
                       COALESCE(t.transport_fc_unitaire, 0)
                FROM requisition_details d
                LEFT JOIN transport_requisition_details t
                    ON t.requisition_detail_id = d.id
                WHERE d.requisition_id = ?
                ORDER BY d.id
            """, (requisition_id,))
            lignes = cur.fetchall()
        finally:
            conn.close()

        if not lignes:
            return 0.0

        dlg = QDialog(fenetre)
        dlg.setWindowTitle("TRANSPORT PAR MARCHANDISE — " + numero_req)
        dlg.resize(900, 520)
        layout = QVBoxLayout(dlg)
        titre_transport = QLabel(
            "TRANSPORT PAR UNITÉ — saisissez le coût d'une unité. "
            "Le total est calculé automatiquement : quantité × transport unitaire."
        )
        titre_transport.setWordWrap(True)
        titre_transport.setStyleSheet(
            "font-size:14px;font-weight:700;padding:8px;color:#2457A6;"
        )
        layout.addWidget(titre_transport)

        tableau_transport = QTableWidget()
        tableau_transport.setColumnCount(4)
        tableau_transport.setHorizontalHeaderLabels([
            "MARCHANDISE", "NOMBRE D'UNITÉS", "TRANSPORT / UNITÉ (FC)",
            "TOTAL TRANSPORT (FC)"
        ])
        appliquer_tableau_standard(tableau_transport)
        tableau_transport.setRowCount(len(lignes))
        tableau_transport.setColumnWidth(0, 260)
        tableau_transport.setColumnWidth(1, 140)
        tableau_transport.setColumnWidth(2, 190)
        tableau_transport.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        champs_transport = []

        total_label = QLabel("TOTAL TRANSPORT : 0 FC")
        total_label.setStyleSheet(
            "font-size:18px;font-weight:800;padding:10px;color:#0F766E;"
        )

        def actualiser_total_transport():
            total = 0.0
            for row, (_, _, quantite, _) in enumerate(lignes):
                champ = champs_transport[row]
                montant = float(quantite or 0) * champ.value()
                total += montant
                item = QTableWidgetItem(formater_nombre(montant) + " FC")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                tableau_transport.setItem(row, 3, item)
            total_label.setText("TOTAL TRANSPORT : " + formater_nombre(total) + " FC")

        for row, ligne in enumerate(lignes):
            detail_id, produit, quantite, transport_unitaire = ligne
            tableau_transport.setItem(row, 0, QTableWidgetItem(str(produit)))
            item_qte = QTableWidgetItem(formater_nombre(quantite))
            item_qte.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tableau_transport.setItem(row, 1, item_qte)

            champ = QDoubleSpinBox()
            champ.setRange(0, 999999999)
            champ.setDecimals(2)
            champ.setSingleStep(100)
            champ.setSuffix(" FC")
            champ.setValue(float(transport_unitaire or 0))
            tableau_transport.setCellWidget(row, 2, champ)
            champs_transport.append(champ)
            champ.valueChanged.connect(actualiser_total_transport)

        layout.addWidget(tableau_transport)
        layout.addWidget(total_label)

        ligne_boutons = QHBoxLayout()
        bouton_sans_transport = QPushButton("FERMER SANS TRANSPORT")
        bouton_sauver_transport = QPushButton("ENREGISTRER LE TRANSPORT")
        bouton_sauver_transport.setStyleSheet(
            "QPushButton{background:#18794E;color:white;font-weight:800;padding:10px;}"
        )
        ligne_boutons.addWidget(bouton_sans_transport)
        ligne_boutons.addStretch()
        ligne_boutons.addWidget(bouton_sauver_transport)
        layout.addLayout(ligne_boutons)

        bouton_sans_transport.clicked.connect(dlg.reject)

        def enregistrer_transport():
            total_transport = sum(
                float(ligne[2] or 0) * champs_transport[i].value()
                for i, ligne in enumerate(lignes)
            )
            conn_save = connexion()
            try:
                cur_save = conn_save.cursor()
                for i, ligne in enumerate(lignes):
                    detail_id, produit, quantite, _ancien = ligne
                    pu_transport = champs_transport[i].value()
                    total_ligne = float(quantite or 0) * pu_transport
                    cur_save.execute("""
                        INSERT INTO transport_requisition_details
                            (requisition_id, requisition_detail_id, produit,
                             quantite, transport_fc_unitaire, total_transport_fc)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(requisition_detail_id) DO UPDATE SET
                            produit = excluded.produit,
                            quantite = excluded.quantite,
                            transport_fc_unitaire = excluded.transport_fc_unitaire,
                            total_transport_fc = excluded.total_transport_fc
                    """, (
                        requisition_id, detail_id, produit, quantite,
                        pu_transport, total_ligne
                    ))
                cur_save.execute("""
                    UPDATE requisitions
                    SET total_transport_fc = ?,
                        total_general_fc = COALESCE(total_fc, 0)
                            + COALESCE(total_declaration_fc, 0) + ?
                    WHERE id = ?
                """, (total_transport, total_transport, requisition_id))
                conn_save.commit()
            except Exception as erreur:
                conn_save.rollback()
                QMessageBox.critical(
                    dlg, "TRANSPORT", "Impossible d'enregistrer le transport :\\n" + str(erreur)
                )
                return
            finally:
                conn_save.close()

            QMessageBox.information(
                dlg, "TRANSPORT ENREGISTRÉ",
                "Transport enregistré.\\n\\nTOTAL TRANSPORT : "
                + formater_nombre(total_transport) + " FC"
            )
            dlg.accept()

        bouton_sauver_transport.clicked.connect(enregistrer_transport)
        actualiser_total_transport()
        dlg.exec()

        conn = connexion()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COALESCE(total_transport_fc, 0) FROM requisitions WHERE id = ?",
                (requisition_id,)
            )
            resultat = cur.fetchone()
            return float(resultat[0] or 0) if resultat else 0.0
        finally:
            conn.close()

    # ========================================================
    # ENREGISTRER
    # ========================================================

    def enregistrer_requisition():

        if not panier_requisition:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "La réquisition est vide."
            )

            return

        confirmation = QMessageBox.question(
            fenetre,
            "ENREGISTRER",
            "Voulez-vous enregistrer cette réquisition ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if confirmation != QMessageBox.StandardButton.Yes:

            return

        total_usd = sum(
            float(article["total_usd"])
            for article in panier_requisition
        )
        total_fc = sum(
            float(article["total_fc"])
            for article in panier_requisition
        )
        total_declaration_fc = sum(
            float(article.get("total_declaration_fc", 0))
            for article in panier_requisition
        )
        total_general_fc = total_fc + total_declaration_fc

        dt = maintenant()

        date_req = dt.strftime(
            "%d/%m/%Y"
        )

        heure_req = dt.strftime(
            "%H:%M:%S"
        )

        conn = connexion()

        try:

            cur = conn.cursor()

            numero_temp = (
                "TEMP-REQ-"
                + dt.strftime(
                    "%Y%m%d%H%M%S%f"
                )
            )

            cur.execute("""
                INSERT INTO requisitions
                (
                    numero_requisition,
                    date,
                    heure,
                    total_fc,
                    total_usd,
                    total_declaration_fc,
                    total_general_fc,
                    statut
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                numero_temp,
                date_req,
                heure_req,
                total_fc,
                total_usd,
                total_declaration_fc,
                total_general_fc,
                "EN ATTENTE"
            ))

            requisition_id = (
                cur.lastrowid
            )

            numero_req = (
                "REQ-"
                + dt.strftime("%Y%m%d")
                + "-"
                + f"{requisition_id:04d}"
            )

            cur.execute("""
                UPDATE requisitions
                SET numero_requisition = ?
                WHERE id = ?
            """, (
                numero_req,
                requisition_id
            ))

            for article in panier_requisition:

                cur.execute("""
                    INSERT INTO requisition_details
                    (
                        requisition_id,
                        produit_id,
                        produit,
                        quantite,
                        prix_achat_usd,
                        prix_achat_fc,
                        total_usd,
                        total_fc,
                        declaration_fc_unitaire,
                        total_declaration_fc,
                        total_general_fc
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    requisition_id,
                    article["id"],
                    article["produit"],
                    article["quantite"],
                    article["prix_usd"],
                    article["prix_fc"],
                    article["total_usd"],
                    article["total_fc"],
                    article.get("declaration_fc_unitaire", 0),
                    article.get("total_declaration_fc", 0),
                    article.get(
                        "total_general_fc",
                        float(article["total_fc"])
                        + float(article.get("total_declaration_fc", 0))
                    )
                ))

            conn.commit()

        except Exception as erreur:

            conn.rollback()

            QMessageBox.critical(
                fenetre,
                "RÉQUISITION",
                "Erreur lors de l'enregistrement :\n"
                + str(erreur)
            )

            conn.close()

            return

        conn.close()

        # Après chaque réquisition, proposer le calcul du transport
        # par unité pour chaque marchandise.
        total_transport_fc = ouvrir_calcul_transport_requisition(
            requisition_id, numero_req
        )
        total_general_fc = total_fc + total_declaration_fc + total_transport_fc

        try:

            enregistrer_journal(
                "RÉQUISITION",
                numero_req,
                "Nouvelle réquisition d'achat",
                total_fc
            )

        except Exception:

            pass

        QMessageBox.information(
            fenetre,
            "RÉQUISITION",
            "Réquisition enregistrée avec succès.\n\n"
            + numero_req
            + "\n\n"
            + "Marchandises : "
            + formater_nombre(total_fc)
            + " FC\n"
            + "Déclarations : "
            + formater_nombre(total_declaration_fc)
            + " FC\n"
            + "Transport : "
            + formater_nombre(total_transport_fc)
            + " FC\n"
            + "TOTAL RÉQUISITION : "
            + formater_nombre(total_general_fc)
            + " FC"
        )

        panier_requisition.clear()

        actualiser_table_requisition()

        charger_produits_requisition()

        charger_historique_requisitions()

    # ========================================================
    # CONNEXIONS RÉQUISITION
    # ========================================================

    bouton_rechercher_req.clicked.connect(
        charger_produits_requisition
    )

    champ_recherche_req.returnPressed.connect(
        charger_produits_requisition
    )

    bouton_ajouter_req.clicked.connect(
        ajouter_produit_requisition
    )

    bouton_ajout_manuel.clicked.connect(
        ajouter_produit_manuellement
    )

    bouton_modifier_req.clicked.connect(
        modifier_produit_requisition
    )

    bouton_supprimer_req.clicked.connect(
        supprimer_produit_requisition
    )
    bouton_vider_req.clicked.connect(
        vider_requisition
    )

    bouton_enregistrer_req.clicked.connect(
        enregistrer_requisition
    )

    # ========================================================
    # PREMIER CHARGEMENT
    # ========================================================

    charger_produits_requisition()

    brouillon_restaure = charger_brouillon_requisition()
    if brouillon_restaure:
        try:
            donnees_brouillon = json.loads(
                fichier_brouillon_requisition.read_text(encoding="utf-8")
            )
            saisie = donnees_brouillon.get("saisie", {})
            champ_prix_usd_requisition.setText(str(saisie.get("prix_usd", "")))
            champ_declaration_requisition.setText(str(saisie.get("declaration_fc", "0") or "0"))
            spin_quantite_requisition.setValue(float(saisie.get("quantite", 1) or 1))
            QMessageBox.information(
                fenetre,
                "BROUILLON RESTAURÉ",
                "Votre réquisition inachevée a été récupérée automatiquement.\\n\\n"
                "Vous pouvez continuer là où vous vous étiez arrêté, ajouter les produits "
                "manquants dans PRODUITS, puis revenir dans ACHATS.\\n\\n"
                "Le brouillon reste distinct des réquisitions définitivement enregistrées."
            )
        except Exception as erreur:
            print("Restauration des champs du brouillon impossible :", erreur)

    champ_prix_usd_requisition.textChanged.connect(sauvegarder_brouillon_requisition)
    champ_declaration_requisition.textChanged.connect(sauvegarder_brouillon_requisition)
    spin_quantite_requisition.valueChanged.connect(sauvegarder_brouillon_requisition)

    actualiser_table_requisition()

    # ========================================================
    # HISTORIQUE
    # ========================================================

    layout_hist = QVBoxLayout(
        page_historique_requisition
    )

    layout_hist.addWidget(
        QLabel(
            "HISTORIQUE DES RÉQUISITIONS"
        )
    )

    table_hist_req = QTableWidget()

    table_hist_req.setColumnCount(7)

    table_hist_req.setHorizontalHeaderLabels([
        "ID",
        "N° RÉQUISITION",
        "DATE",
        "HEURE",
        "TOTAL FC",
        "TOTAL $",
        "STATUT"
    ])

    appliquer_tableau_standard(
        table_hist_req
    )

    layout_hist.addWidget(
        table_hist_req
    )

    layout_hist.addWidget(
        QLabel("CONTENU")
    )

    table_details_req = QTableWidget()

    table_details_req.setColumnCount(9)

    table_details_req.setHorizontalHeaderLabels([
        "PRODUIT",
        "QTÉ",
        "PU $",
        "PU FC",
        "TOTAL $",
        "TOTAL FC",
        "DÉCL./UNITÉ FC",
        "TOTAL DÉCL. FC",
        "TOTAL MARCHANDISE FC"
    ])

    appliquer_tableau_standard(
        table_details_req
    )

    layout_hist.addWidget(
        table_details_req
    )

    # ========================================================
    # BOUTONS HISTORIQUE
    # ========================================================

    ligne_hist_actions = QHBoxLayout()

    bouton_reutiliser_req = QPushButton(
        "RÉUTILISER LA RÉQUISITION"
    )

    bouton_pdf_hist_req = QPushButton(
        "PDF"
    )

    bouton_supprimer_hist_req = QPushButton(
        "SUPPRIMER"
    )

    ligne_hist_actions.addWidget(
        bouton_reutiliser_req
    )

    ligne_hist_actions.addWidget(
        bouton_pdf_hist_req
    )

    ligne_hist_actions.addWidget(
        bouton_supprimer_hist_req
    )

    layout_hist.addLayout(
        ligne_hist_actions
    )

    # ========================================================
    # CHARGER HISTORIQUE
    # ========================================================

    def charger_historique_requisitions():

        conn = connexion()

        try:

            cur = conn.cursor()

            cur.execute("""
                SELECT
                    id,
                    numero_requisition,
                    date,
                    heure,
                    total_fc,
                    total_usd,
                    statut
                FROM requisitions
                ORDER BY id DESC
            """)

            lignes = cur.fetchall()

        finally:

            conn.close()

        table_hist_req.clearContents()

        table_hist_req.setRowCount(
            len(lignes)
        )

        for row, ligne in enumerate(
            lignes
        ):

            ajouter_ligne_tableau(
                table_hist_req,
                row,
                [
                    ligne[0],
                    ligne[1],
                    ligne[2],
                    ligne[3],
                    formater_nombre(
                        ligne[4]
                    ) + " FC",
                    f"{float(ligne[5] or 0):.2f} $",
                    ligne[6]
                ]
            )

        table_details_req.clearContents()

        table_details_req.setRowCount(
            0
        )

    # ========================================================
    # DÉTAILS HISTORIQUE
    # ========================================================

    def afficher_details_requisition():

        row = (
            table_hist_req
            .currentRow()
        )

        if row < 0:

            return

        item = (
            table_hist_req
            .item(row, 0)
        )

        if item is None:

            return

        requisition_id = int(
            item.text()
        )

        conn = connexion()

        try:

            cur = conn.cursor()

            cur.execute("""
                SELECT
                    produit,
                    quantite,
                    prix_achat_usd,
                    prix_achat_fc,
                    total_usd,
                    total_fc,
                    declaration_fc_unitaire,
                    total_declaration_fc,
                    total_general_fc
                FROM requisition_details
                WHERE requisition_id = ?
                ORDER BY id
            """, (
                requisition_id,
            ))

            details = cur.fetchall()

        finally:

            conn.close()

        table_details_req.clearContents()

        table_details_req.setRowCount(
            len(details)
        )

        for row, detail in enumerate(
            details
        ):

            ajouter_ligne_tableau(
                table_details_req,
                row,
                [
                    detail[0],
                    formater_nombre(
                        detail[1]
                    ),
                    f"{float(detail[2] or 0):.2f} $",
                    formater_nombre(
                        detail[3]
                    ) + " FC",
                    f"{float(detail[4] or 0):.2f} $",
                    formater_nombre(
                        detail[5]
                    ) + " FC",
                    formater_nombre(
                        detail[6]
                    ) + " FC",
                    formater_nombre(
                        detail[7]
                    ) + " FC",
                    formater_nombre(
                        detail[8] or (
                            float(detail[5] or 0)
                            + float(detail[7] or 0)
                        )
                    ) + " FC"
                ]
            )

    # ========================================================
    # RÉUTILISER
    # ========================================================

    def reutiliser_requisition():

        row = (
            table_hist_req
            .currentRow()
        )

        if row < 0:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Sélectionnez une réquisition."
            )

            return

        item = (
            table_hist_req
            .item(row, 0)
        )

        if item is None:

            return

        requisition_id = int(
            item.text()
        )

        conn = connexion()

        try:

            cur = conn.cursor()

            cur.execute("""
                SELECT
                    produit_id,
                    produit,
                    quantite,
                    prix_achat_usd,
                    prix_achat_fc,
                    total_usd,
                    total_fc,
                    declaration_fc_unitaire,
                    total_declaration_fc,
                    total_general_fc
                FROM requisition_details
                WHERE requisition_id = ?
                ORDER BY id
            """, (
                requisition_id,
            ))

            details = cur.fetchall()

        finally:

            conn.close()

        if not details:

            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Cette réquisition ne contient aucun produit."
            )

            return

        panier_requisition.clear()

        for detail in details:

            panier_requisition.append({
                "id": detail[0],
                "produit": detail[1],
                "quantite": float(
                    detail[2] or 0
                ),
                "prix_usd": float(
                    detail[3] or 0
                ),
                "prix_fc": float(
                    detail[4] or 0
                ),
                "total_usd": float(
                    detail[5] or 0
                ),
                "total_fc": float(
                    detail[6] or 0
                ),
                "declaration_fc_unitaire": float(
                    detail[7] or 0
                ),
                "total_declaration_fc": float(
                    detail[8] or 0
                ),
                "total_general_fc": float(
                    detail[9] or (
                        float(detail[6] or 0)
                        + float(detail[8] or 0)
                    )
                )
            })

        actualiser_table_requisition()

        onglets_achats.setCurrentWidget(
            page_requisition
        )

        QMessageBox.information(
            fenetre,
            "RÉQUISITION",
            "La réquisition a été réutilisée."
        )

    # ========================================================
    # SUPPRIMER HISTORIQUE
    # ========================================================

    def supprimer_requisition_historique():

        row = (
            table_hist_req
            .currentRow()
        )

        if row < 0:
            QMessageBox.warning(
                fenetre,
                "RÉQUISITION",
                "Sélectionnez une réquisition."
            )

            return

        item = (
            table_hist_req
            .item(row, 0)
        )

        if item is None:

            return

        requisition_id = int(
            item.text()
        )

        confirmation = QMessageBox.question(
            fenetre,
            "SUPPRIMER",
            "Voulez-vous supprimer cette réquisition ?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if confirmation != QMessageBox.StandardButton.Yes:

            return

        conn = connexion()

        try:

            cur = conn.cursor()

            cur.execute("""
                DELETE FROM requisition_details
                WHERE requisition_id = ?
            """, (
                requisition_id,
            ))

            cur.execute("""
                DELETE FROM requisitions
                WHERE id = ?
            """, (
                requisition_id,
            ))

            conn.commit()

        except Exception as erreur:

            conn.rollback()

            QMessageBox.critical(
                fenetre,
                "SUPPRESSION",
                "Erreur :\n"
                + str(erreur)
            )

            conn.close()

            return

        conn.close()

        charger_historique_requisitions()

        QMessageBox.information(
            fenetre,
            "RÉQUISITION",
            "Réquisition supprimée."
        )

    # ========================================================
    # PDF HISTORIQUE
    # ========================================================

    def pdf_requisition_selectionnee():

        row = (
            table_hist_req
            .currentRow()
        )

        if row < 0:

            QMessageBox.warning(
                fenetre,
                "PDF",
                "Sélectionnez d'abord une réquisition."
            )

            return

        item = (
            table_hist_req
            .item(row, 0)
        )

        if item is None:

            return

        requisition_pdf(
            int(item.text())
        )

    # ========================================================
    # CONNEXIONS HISTORIQUE
    # ========================================================

    table_hist_req.itemSelectionChanged.connect(
        afficher_details_requisition
    )
    table_hist_req.cellDoubleClicked.connect(
        lambda row, column: afficher_details_requisition()
    )

    bouton_reutiliser_req.clicked.connect(
        reutiliser_requisition
    )

    bouton_pdf_hist_req.clicked.connect(
        pdf_requisition_selectionnee
    )

    bouton_supprimer_hist_req.clicked.connect(
        supprimer_requisition_historique
    )

    charger_historique_requisitions()

    # ========================================================
    # DASHBOARD ACHATS
    # ========================================================

    layout_dashboard = QVBoxLayout(
        page_dashboard_achats
    )

    layout_dashboard.addWidget(
        creer_titre(
            "DASHBOARD DES ACHATS",
            24
        )
    )

    conn = connexion()

    try:

        cur = conn.cursor()

        # ----------------------------------------------------
        # NOMBRE DE RÉQUISITIONS
        # ----------------------------------------------------

        cur.execute("""
            SELECT COUNT(*)
            FROM requisitions
        """)

        nombre_requisitions = (
            cur.fetchone()[0]
        )

        # ----------------------------------------------------
        # TOTAL ACHATS
        # ----------------------------------------------------

        cur.execute("""
            SELECT
                COALESCE(SUM(COALESCE(total_general_fc, total_fc)), 0),
                COALESCE(SUM(total_usd), 0)
            FROM requisitions
        """)

        total_achats_fc, total_achats_usd = (
            cur.fetchone()
        )
        # ----------------------------------------------------
        # ACHATS DU JOUR
        # ----------------------------------------------------

        aujourd_hui = datetime.now().strftime(
            "%d/%m/%Y"
        )

        cur.execute("""
            SELECT
                COALESCE(SUM(COALESCE(total_general_fc, total_fc)), 0),
                COALESCE(SUM(total_usd), 0)
            FROM requisitions
            WHERE date = ?
        """, (
            aujourd_hui,
        ))

        achats_jour_fc, achats_jour_usd = (
            cur.fetchone()
        )

        # ----------------------------------------------------
        # ACHATS DU MOIS
        # ----------------------------------------------------

        mois = datetime.now().strftime(
            "%m/%Y"
        )

        cur.execute("""
            SELECT
                COALESCE(SUM(COALESCE(total_general_fc, total_fc)), 0),
                COALESCE(SUM(total_usd), 0)
            FROM requisitions
            WHERE substr(date, 4, 7) = ?
        """, (
            mois,
        ))

        achats_mois_fc, achats_mois_usd = (
            cur.fetchone()
        )

        # ----------------------------------------------------
        # ARTICLES RÉQUISITIONNÉS
        # ----------------------------------------------------

        cur.execute("""
            SELECT
                COALESCE(SUM(quantite), 0)
            FROM requisition_details
        """)

        articles_requisitionnes = (
            cur.fetchone()[0]
        )

    finally:

        conn.close()

    # ========================================================
    # CARTES DASHBOARD
    # ========================================================

    grille_achats = QGridLayout()

    cartes_achats = [

        (
            "NOMBRE DE RÉQUISITIONS",
            formater_nombre(
                nombre_requisitions
            )
        ),

        (
            "TOTAL ACHATS",
            formater_nombre(
                total_achats_fc
            )
            + " FC"
        ),

        (
            "TOTAL ACHATS ($)",
            f"{float(total_achats_usd or 0):,.2f} $"
        ),

        (
            "ACHATS DU JOUR",
            formater_nombre(
                achats_jour_fc
            )
            + " FC"
        ),

        (
            "ACHATS DU MOIS",
            formater_nombre(
                achats_mois_fc
            )
            + " FC"
        ),

        (
            "ARTICLES RÉQUISITIONNÉS",
            formater_nombre(
                articles_requisitionnes
            )
        )
    ]

    for i, (nom, valeur) in enumerate(cartes_achats):
        grille_achats.addWidget(
            creer_carte_dashboard(nom, valeur, i),
            i // 3,
            i % 3
        )

    layout_dashboard.addLayout(grille_achats)
    conn_graph = connexion()
    cur_graph = conn_graph.cursor()
    cur_graph.execute("SELECT date, COALESCE(SUM(total_fc), 0) FROM requisitions GROUP BY date")
    achats_par_date = cur_graph.fetchall()
    conn_graph.close()
    auj = date.today()
    jours = [(auj - timedelta(days=6-i)) for i in range(7)]
    index = {}
    for date_txt, montant in achats_par_date:
        try:
            d = datetime.strptime(str(date_txt), "%d/%m/%Y").date()
            index[d] = index.get(d, 0) + float(montant or 0)
        except (ValueError, TypeError):
            continue
    graph_achats = GraphiqueVentes([d.strftime("%d/%m") for d in jours], [index.get(d, 0) for d in jours], titre="ÉVOLUTION DES ACHATS — 7 DERNIERS JOURS")
    graph_achats.setStyleSheet("background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;")
    layout_dashboard.addWidget(graph_achats)
    layout_dashboard.addStretch()

    # ========================================================
    # MEILLEURE RÉQUISITION
    # ========================================================
    def construire_page_requisition_classee(page, titre, ordre):
        layout = QVBoxLayout(page)
        layout.addWidget(creer_titre(titre, 24))

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "RANG", "N° RÉQUISITION", "DATE", "HEURE",
            "NET À PAYER (FC)", "NET À PAYER ($)"
        ])
        appliquer_tableau_standard(table)
        layout.addWidget(table)

        conn = connexion()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id, numero_requisition, date, heure,
                   COALESCE(total_general_fc, total_fc) AS total_net_fc,
                   total_usd
            FROM requisitions
            ORDER BY COALESCE(total_general_fc, total_fc) {ordre}, id DESC
            LIMIT 1
        """)
        ligne = cur.fetchone()
        conn.close()

        if ligne:
            table.setRowCount(1)
            ajouter_ligne_tableau(table, 0, [
                "1",
                ligne[1],
                ligne[2],
                ligne[3],
                formater_nombre(ligne[4] or 0) + " FC",
                f"{float(ligne[5] or 0):.2f} $",
            ])
        else:
            table.setRowCount(1)
            ajouter_ligne_tableau(table, 0, [
                "—", "Aucune réquisition", "—", "—", "0 FC", "0.00 $"
            ])

        layout.addStretch()

    construire_page_requisition_classee(
        page_meilleure_requisition,
        "MEILLEURE RÉQUISITION",
        "DESC"
    )
    construire_page_requisition_classee(
        page_requisition_faible,
        "RÉQUISITION TROP FAIBLE",
        "ASC"
    )
# ============================================================
# CALCULS FINANCIERS
# ============================================================

def valeur_stock_pa():
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(prix_achat_fc * stock), 0)
        FROM produits
        WHERE visible = 1
    """)
    valeur = cur.fetchone()[0]
    conn.close()
    return float(valeur or 0)


def valeur_stock_pv():
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(prix_fc * stock), 0)
        FROM produits
        WHERE visible = 1
    """)
    valeur = cur.fetchone()[0]
    conn.close()
    return float(valeur or 0)


def benefice_global():
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM((prix_fc - prix_achat_fc) * quantite), 0)
        FROM vente_details
    """)
    valeur = cur.fetchone()[0]
    conn.close()
    return float(valeur or 0)


def benefice_periode(date_debut, date_fin):
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(
            (vd.prix_fc - vd.prix_achat_fc) * vd.quantite
        ), 0)
        FROM vente_details vd
        JOIN ventes v ON v.id = vd.vente_id
        WHERE substr(v.date, 7, 4) || '-' ||
              substr(v.date, 4, 2) || '-' ||
              substr(v.date, 1, 2)
              BETWEEN ? AND ?
    """, (date_debut, date_fin))
    valeur = cur.fetchone()[0]
    conn.close()
    return float(valeur or 0)


def produit_plus_rentable():
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            produit,
            COALESCE(SUM((prix_fc - prix_achat_fc) * quantite), 0) AS benefice
        FROM vente_details
        GROUP BY produit
        ORDER BY benefice DESC
        LIMIT 1
    """)
    resultat = cur.fetchone()
    conn.close()
    return resultat if resultat else ("—", 0)


def marge_moyenne():
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COALESCE(SUM((prix_fc - prix_achat_fc) * quantite), 0),
            COALESCE(SUM(prix_fc * quantite), 0)
        FROM vente_details
    """)
    benefice, ca = cur.fetchone()
    conn.close()
    if not ca:
        return 0
    return float(benefice or 0) / float(ca) * 100


# ============================================================
# DASHBOARD DES VENTES
# ============================================================

def charger_stats_ventes():
    conn = connexion()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM ventes")
    nb_ventes = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(total_fc), 0) FROM ventes")
    ca = cur.fetchone()[0]

    cur.execute("SELECT COALESCE(SUM(quantite), 0) FROM vente_details")
    articles = cur.fetchone()[0]

    aujourd_hui = datetime.now().strftime("%d/%m/%Y")
    cur.execute("SELECT COALESCE(SUM(total_fc), 0) FROM ventes WHERE date = ?", (aujourd_hui,))
    ca_jour = cur.fetchone()[0]

    mois = datetime.now().strftime("%m/%Y")
    cur.execute("""
        SELECT COALESCE(SUM(total_fc), 0)
        FROM ventes
        WHERE substr(date, 4, 7) = ?
    """, (mois,))
    ca_mois = cur.fetchone()[0]

    cur.execute("""
        SELECT produit, COALESCE(SUM(quantite), 0) AS qte
        FROM vente_details
        GROUP BY produit
        ORDER BY qte DESC
        LIMIT 1
    """)
    top = cur.fetchone()
    top_produit = top[0] if top else "—"

    conn.close()
    return nb_ventes, ca, articles, ca_jour, ca_mois, top_produit


def construire_dashboard_ventes(page):
    layout = QVBoxLayout(page)
    layout.addWidget(creer_titre("DASHBOARD DES VENTES", 24))

    grille = QGridLayout()
    stats = charger_stats_ventes()

    rubriques = [
        ("🧾  NOMBRE DE VENTES", formater_nombre(stats[0])),
        ("💰  CHIFFRE D'AFFAIRES", formater_nombre(stats[1]) + " FC"),
        ("🛍️  ARTICLES VENDUS", formater_nombre(stats[2])),
        ("📅  VENTE DU JOUR", formater_nombre(stats[3]) + " FC"),
        ("📈  VENTE DU MOIS", formater_nombre(stats[4]) + " FC"),
        ("⭐  TOP PRODUIT", stats[5]),
    ]

    for index, (rubrique, valeur) in enumerate(rubriques):
        grille.addWidget(creer_carte_dashboard(rubrique, valeur, index), index // 3, index % 3)

    layout.addLayout(grille)
    conn_graph = connexion()
    cur_graph = conn_graph.cursor()
    cur_graph.execute("SELECT date, COALESCE(SUM(total_fc), 0) FROM ventes GROUP BY date")
    ventes_par_date = cur_graph.fetchall()
    conn_graph.close()
    auj = date.today()
    jours = [(auj - timedelta(days=6-i)) for i in range(7)]
    index = {}
    for date_txt, montant in ventes_par_date:
        try:
            d = datetime.strptime(str(date_txt), "%d/%m/%Y").date()
            index[d] = index.get(d, 0) + float(montant or 0)
        except (ValueError, TypeError):
            continue
    graph_ventes = GraphiqueVentes([d.strftime("%d/%m") for d in jours], [index.get(d, 0) for d in jours])
    graph_ventes.setStyleSheet("background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;")
    layout.addWidget(graph_ventes)
    layout.addStretch()


# ============================================================
# VENTES
# ============================================================

def facture_pdf_vente(vente_id):
    """Génère une facture A4 plus professionnelle, sans modifier les données de vente."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.lib import colors
    except ImportError:
        QMessageBox.warning(fenetre, "FACTURE PDF", "ReportLab n'est pas installé. Installez-le avec : pip install reportlab")
        return

    conn = connexion()
    cur = conn.cursor()
    cur.execute("SELECT numero_vente, date, heure, nom_client, total_fc, total_usd FROM ventes WHERE id = ?", (vente_id,))
    vente = cur.fetchone()
    if vente is None:
        conn.close()
        QMessageBox.warning(fenetre, "FACTURE PDF", "Vente introuvable.")
        return
    cur.execute("SELECT produit, prix_fc, quantite, total_fc FROM vente_details WHERE vente_id = ? ORDER BY id", (vente_id,))
    details = cur.fetchall()
    conn.close()

    numero, date_vente, heure_vente, nom_client, total_fc, total_usd = vente
    dossier_pdf = RAPPORTS_PDF_DIR
    dossier_pdf.mkdir(parents=True, exist_ok=True)
    nom_fichier = dossier_pdf / f"Facture_{numero}.pdf"
    c = canvas.Canvas(str(nom_fichier), pagesize=A4)
    largeur, hauteur = A4
    bleu = colors.HexColor('#17365D')
    bleu_clair = colors.HexColor('#EAF1F8')
    gris = colors.HexColor('#64748B')
    marge_g = 18 * mm
    marge_d = largeur - 18 * mm

    # En-tête de marque
    c.setFillColor(bleu)
    c.roundRect(marge_g, hauteur - 43*mm, largeur - 36*mm, 28*mm, 3*mm, fill=1, stroke=0)
    if LOGO_PATH.exists():
        try:
            c.drawImage(str(LOGO_PATH), marge_g + 5*mm, hauteur - 39*mm, width=19*mm, height=19*mm, preserveAspectRatio=True, anchor='c', mask='auto')
        except Exception:
            pass
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 17)
    c.drawString(marge_g + 29*mm, hauteur - 25*mm, obtenir_message_accueil_pdf())
    c.setFont('Helvetica', 9)
    c.drawString(marge_g + 29*mm, hauteur - 33*mm, 'FACTURE DE VENTE')
    c.setFont('Helvetica-Bold', 16)
    c.drawRightString(marge_d - 5*mm, hauteur - 25*mm, 'FACTURE')

    y = hauteur - 55*mm
    c.setFillColor(bleu)
    c.setFont('Helvetica-Bold', 10)
    c.drawString(marge_g, y, 'INFORMATIONS DE FACTURATION')
    y -= 3*mm
    c.setStrokeColor(colors.HexColor('#CBD5E1'))
    c.line(marge_g, y, marge_d, y)
    y -= 8*mm
    c.setFillColor(colors.HexColor('#1F2937'))
    c.setFont('Helvetica-Bold', 9)
    c.drawString(marge_g, y, 'N° FACTURE')
    c.drawString(105*mm, y, 'DATE ET HEURE')
    y -= 6*mm
    c.setFont('Helvetica', 10)
    c.drawString(marge_g, y, str(numero))
    c.drawString(105*mm, y, f'{date_vente}  |  {heure_vente}')
    y -= 9*mm
    c.setFont('Helvetica-Bold', 9)
    c.drawString(marge_g, y, 'CLIENT')
    y -= 6*mm
    c.setFont('Helvetica', 10)
    c.drawString(marge_g, y, (nom_client or 'Client comptant')[:75])
    y -= 12*mm

    # Tableau lisible avec lignes alternées et montants alignés
    c.setFillColor(bleu)
    c.roundRect(marge_g, y-7*mm, largeur-36*mm, 9*mm, 1.5*mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(marge_g+3*mm, y-4*mm, 'DÉSIGNATION')
    c.drawRightString(132*mm, y-4*mm, 'PRIX UNITAIRE (FC)')
    c.drawRightString(155*mm, y-4*mm, 'QTÉ')
    c.drawRightString(marge_d-3*mm, y-4*mm, 'TOTAL (FC)')
    y -= 10*mm
    for idx, (produit, prix, quantite, total) in enumerate(details):
        if y < 42*mm:
            c.showPage()
            y = hauteur - 22*mm
            c.setFillColor(bleu); c.roundRect(marge_g, y-7*mm, largeur-36*mm, 9*mm, 1.5*mm, fill=1, stroke=0)
            c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 8.5)
            c.drawString(marge_g+3*mm, y-4*mm, 'DÉSIGNATION')
            c.drawRightString(132*mm, y-4*mm, 'PRIX UNITAIRE (FC)')
            c.drawRightString(155*mm, y-4*mm, 'QTÉ')
            c.drawRightString(marge_d-3*mm, y-4*mm, 'TOTAL (FC)')
            y -= 10*mm
        if idx % 2 == 0:
            c.setFillColor(bleu_clair)
            c.rect(marge_g, y-5.5*mm, largeur-36*mm, 7*mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor('#1F2937'))
        c.setFont('Helvetica', 8.5)
        c.drawString(marge_g+3*mm, y-1*mm, str(produit)[:48])
        c.drawRightString(132*mm, y-1*mm, formater_nombre(prix))
        c.drawRightString(155*mm, y-1*mm, formater_nombre(quantite))
        c.setFont('Helvetica-Bold', 8.5)
        c.drawRightString(marge_d-3*mm, y-1*mm, formater_nombre(total))
        y -= 7*mm

    y -= 8*mm
    c.setStrokeColor(colors.HexColor('#CBD5E1'))
    c.line(105*mm, y, marge_d, y)
    y -= 9*mm
    c.setFillColor(bleu)
    c.setFont('Helvetica-Bold', 11)
    c.drawString(110*mm, y, 'TOTAL À PAYER')
    c.setFont('Helvetica-Bold', 14)
    c.drawRightString(marge_d, y, formater_nombre(total_fc) + ' FC')
    y -= 8*mm
    c.setFillColor(gris)
    c.setFont('Helvetica', 10)
    c.drawRightString(marge_d, y, f'{float(total_usd or 0):,.2f} $'.replace(',', ' '))

    c.setStrokeColor(colors.HexColor('#CBD5E1'))
    c.line(marge_g, 23*mm, marge_d, 23*mm)
    c.setFillColor(gris)
    c.setFont('Helvetica-Oblique', 8)
    c.drawString(marge_g, 17*mm, 'Merci pour votre confiance.')
    c.drawRightString(marge_d, 17*mm, obtenir_message_accueil_pdf())
    c.save()
    QMessageBox.information(fenetre, 'FACTURE PDF', f'Facture professionnelle générée :\n{nom_fichier}')
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(nom_fichier)))


def coloriser_onglets_ventes(onglets):
    """Donne une identité visuelle différente aux trois pages de Ventes."""
    pages = [
        (onglets.widget(0), "#EFF6FF", "#2563EB"),
        (onglets.widget(1), "#F0FDF4", "#16A34A"),
        (onglets.widget(2), "#FAF5FF", "#7C3AED"),
        (onglets.widget(3), "#FFF7ED", "#EA580C"),
        (onglets.widget(4), "#F0FDF4", "#16A34A"),
        (onglets.widget(5), "#EEF2FF", "#4338CA"),
    ]

    for index, (page, fond, texte) in enumerate(pages):
        if page is not None:
            page.setStyleSheet(
                f"QWidget {{ background-color: {fond}; }}"
            )
        onglets.tabBar().setTabTextColor(index, texte)

    onglets.setStyleSheet("""
        QTabBar::tab {
            padding: 10px 16px;
            font-weight: bold;
            border: 1px solid #CBD5E1;
            border-bottom: none;
            background: #E2E8F0;
        }
        QTabBar::tab:selected {
            background: #FFFFFF;
        }
        QTabWidget::pane {
            border: 1px solid #CBD5E1;
        }
    """)


def generer_pdf_rapport_journalier(date_selectionnee=None):
    """Génère un PDF professionnel pour la date choisie, pas uniquement aujourd'hui."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        from reportlab.lib import colors
    except ImportError:
        QMessageBox.warning(fenetre, "Rapport PDF", "ReportLab manque. Installez-le avec : pip install reportlab")
        return

    date_cible = date_selectionnee or datetime.now().strftime('%d/%m/%Y')
    try:
        date_iso = datetime.strptime(date_cible, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError:
        QMessageBox.warning(fenetre, 'Rapport PDF', 'La date choisie est invalide.')
        return
    conn = connexion()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), COALESCE(SUM(total_fc),0), COALESCE(SUM(total_usd),0) FROM ventes WHERE date=?", (date_cible,))
    nb_ventes, ca_fc, ca_usd = cur.fetchone()
    cur.execute("SELECT COALESCE(SUM(quantite),0) FROM vente_details vd JOIN ventes v ON v.id=vd.vente_id WHERE v.date=?", (date_cible,))
    articles = cur.fetchone()[0]
    cur.execute("SELECT heure, operation, reference, description, montant FROM journal WHERE date=? ORDER BY id DESC", (date_cible,))
    activites = cur.fetchall()
    cur.execute("SELECT horodatage, operation, reference, description, montant FROM audit_events WHERE substr(horodatage,1,10)=? ORDER BY id DESC", (date_iso,))
    audits = cur.fetchall()
    conn.close()

    RAPPORTS_PDF_DIR.mkdir(parents=True, exist_ok=True)
    nom = f"Rapport_journalier_{datetime.strptime(date_cible, '%d/%m/%Y').strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}.pdf"
    chemin = RAPPORTS_PDF_DIR / nom
    c = canvas.Canvas(str(chemin), pagesize=A4)
    largeur, hauteur = A4
    bleu = colors.HexColor('#17365D')
    bleu_clair = colors.HexColor('#EAF1F8')
    gris = colors.HexColor('#64748B')
    mg, md = 18*mm, largeur-18*mm
    c.setTitle(f'Rapport journalier - {date_cible}')
    c.setFillColor(bleu); c.roundRect(mg, hauteur-43*mm, largeur-36*mm, 27*mm, 3*mm, fill=1, stroke=0)
    if LOGO_PATH.exists():
        try: c.drawImage(str(LOGO_PATH), mg+4*mm, hauteur-39*mm, width=18*mm, height=18*mm, preserveAspectRatio=True, mask='auto')
        except Exception: pass
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 16); c.drawString(mg+27*mm, hauteur-25*mm, obtenir_message_accueil_pdf())
    c.setFont('Helvetica', 9); c.drawString(mg+27*mm, hauteur-33*mm, 'RAPPORT JOURNALIER D’ACTIVITÉ')
    y = hauteur-54*mm
    c.setFillColor(bleu); c.setFont('Helvetica-Bold', 11); c.drawString(mg, y, f'JOURNÉE DU {date_cible}')
    c.setFillColor(gris); c.setFont('Helvetica', 8); c.drawRightString(md, y, 'Généré le ' + datetime.now().strftime('%d/%m/%Y à %H:%M'))
    y -= 10*mm
    stats = [('VENTES', str(nb_ventes)), ('CHIFFRE D’AFFAIRES', formater_nombre(ca_fc)+' FC'), ('CA EN USD', f'{float(ca_usd or 0):.2f} $'), ('ARTICLES VENDUS', formater_nombre(articles))]
    box_w=(largeur-36*mm-6*mm)/2
    for i,(lab,val) in enumerate(stats):
        x=mg+(i%2)*(box_w+6*mm); yy=y-(i//2)*17*mm
        c.setFillColor(bleu_clair); c.roundRect(x, yy-12*mm, box_w, 14*mm, 2*mm, fill=1, stroke=0)
        c.setFillColor(bleu); c.setFont('Helvetica-Bold', 8); c.drawString(x+4*mm, yy-3*mm, lab)
        c.setFont('Helvetica-Bold', 11); c.drawRightString(x+box_w-4*mm, yy-9*mm, val)
    y -= 38*mm

    def section(titre, rows, headers):
        nonlocal y
        if y < 42*mm:
            c.showPage(); y=hauteur-20*mm
        c.setFillColor(bleu); c.setFont('Helvetica-Bold', 10); c.drawString(mg, y, titre)
        y -= 6*mm
        col_x=[mg, 45*mm, 78*mm, 112*mm, md]
        c.setFillColor(bleu); c.roundRect(mg, y-5*mm, largeur-36*mm, 7*mm, 1*mm, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 7)
        for x,h in zip(col_x,headers):
            if x == md: c.drawRightString(x-2*mm,y-2.5*mm,str(h)[:20])
            else: c.drawString(x+2*mm,y-2.5*mm,str(h)[:22])
        y -= 8*mm
        for idx,row in enumerate(rows):
            if y < 18*mm:
                c.showPage(); y=hauteur-20*mm
            vals=[str(v or '').replace('\n',' ') for v in row]
            if idx%2==0:
                c.setFillColor(bleu_clair); c.rect(mg,y-3.5*mm,largeur-36*mm,5*mm,fill=1,stroke=0)
            c.setFillColor(colors.HexColor('#1F2937')); c.setFont('Helvetica',6.5)
            for j,(x,v) in enumerate(zip(col_x,vals)):
                v=v[:32]
                if j==4: c.drawRightString(x-2*mm,y-1.5*mm,v)
                else: c.drawString(x+2*mm,y-1.5*mm,v)
            y -= 5*mm
        if not rows:
            c.setFillColor(gris); c.setFont('Helvetica-Oblique',8); c.drawString(mg+2*mm,y-1*mm,'Aucune donnée enregistrée pour cette journée.')
            y -= 6*mm
        y -= 7*mm
    section('ACTIVITÉS DE LA JOURNÉE', activites, ['Heure','Opération','Référence','Description','Montant FC'])
    section('TRACE TECHNIQUE / AUDIT', audits, ['Horodatage','Opération','Référence','Description','Montant FC'])
    c.setStrokeColor(colors.HexColor('#CBD5E1')); c.line(mg, 15*mm, md, 15*mm)
    c.setFillColor(gris); c.setFont('Helvetica-Oblique', 7)
    c.drawString(mg, 10*mm, "Document généré automatiquement par " + obtenir_message_accueil_pdf())
    c.drawRightString(md, 10*mm, 'Page de synthèse')
    c.save()
    QMessageBox.information(fenetre, 'Rapport PDF créé', f'Rapport du {date_cible} enregistré dans :\n{chemin}')
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin)))
    return chemin


def afficher_liste_rapports_pdf(page):
    """Liste les rapports PDF archivés et permet de les ouvrir."""
    layout=QVBoxLayout(page)
    layout.addWidget(creer_titre("ARCHIVE DES RAPPORTS PDF", 22))
    info=QLabel(f"Dossier d'archivage : {RAPPORTS_PDF_DIR}"); info.setWordWrap(True); layout.addWidget(info)
    table=QTableWidget(); table.setColumnCount(3); table.setHorizontalHeaderLabels(["FICHIER PDF","DATE DE CRÉATION","ACTION"])
    appliquer_tableau_standard(table)
    fichiers=sorted(RAPPORTS_PDF_DIR.glob("*.pdf"), key=lambda x:x.stat().st_mtime, reverse=True)
    table.setRowCount(len(fichiers))
    for i,f in enumerate(fichiers):
        table.setItem(i,0,QTableWidgetItem(f.name))
        table.setItem(i,1,QTableWidgetItem(datetime.fromtimestamp(f.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S")))
        btn=QPushButton("OUVRIR PDF"); btn.clicked.connect(lambda checked=False, chemin=f: QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin))))
        table.setCellWidget(i,2,btn)
    layout.addWidget(table)
    ligne=QHBoxLayout(); actualiser=QPushButton("ACTUALISER LA LISTE"); ouvrir_dossier=QPushButton("OUVRIR LE DOSSIER")
    actualiser.clicked.connect(lambda: (layout.removeWidget(table), table.deleteLater(), afficher_liste_rapports_pdf(page)))
    ouvrir_dossier.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(RAPPORTS_PDF_DIR))))
    ligne.addWidget(actualiser); ligne.addWidget(ouvrir_dossier); layout.addLayout(ligne)


def afficher_rapport_journalier_ventes(page):
    """Affiche le rapport d'une date librement sélectionnée, avec export PDF."""
    layout = QVBoxLayout(page)
    layout.addWidget(creer_titre('RAPPORT JOURNALIER', 24))

    ligne_date = QHBoxLayout()
    ligne_date.addWidget(QLabel('Choisir la journée :'))
    date_rapport = QDateEdit()
    date_rapport.setCalendarPopup(True)
    date_rapport.setDisplayFormat('dd/MM/yyyy')
    date_rapport.setDate(QDate.currentDate())
    date_rapport.setMinimumWidth(150)
    bouton_afficher = QPushButton('🔎 AFFICHER LE RAPPORT')
    bouton_pdf = QPushButton('📄 GÉNÉRER LE PDF DE CETTE JOURNÉE')
    bouton_pdf.setStyleSheet('font-weight: bold; padding: 10px; background: #17365D; color: white; border-radius: 6px;')
    ligne_date.addWidget(date_rapport)
    ligne_date.addWidget(bouton_afficher)
    ligne_date.addWidget(bouton_pdf)
    ligne_date.addStretch()
    layout.addLayout(ligne_date)

    zone_rapport = QWidget()
    zone_layout = QVBoxLayout(zone_rapport)
    layout.addWidget(zone_rapport)

    def charger_rapport():
        while zone_layout.count():
            item = zone_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        date_cible = date_rapport.date().toString('dd/MM/yyyy')
        zone_layout.addWidget(QLabel(f'Rapport de la journée : {date_cible}'))
        grille = QGridLayout()
        conn = connexion(); cur = conn.cursor()
        cur.execute('SELECT COUNT(*), COALESCE(SUM(total_fc),0), COALESCE(SUM(total_usd),0) FROM ventes WHERE date=?', (date_cible,))
        nb_ventes, ca_fc, ca_usd = cur.fetchone()
        cur.execute('SELECT COALESCE(SUM(quantite),0) FROM vente_details vd JOIN ventes v ON v.id=vd.vente_id WHERE v.date=?', (date_cible,))
        articles = cur.fetchone()[0]
        cur.execute('SELECT COUNT(*) FROM journal WHERE date=?', (date_cible,)); nb_activites=cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM journal WHERE date=? AND operation IN ('VIDER STOCK','MODIFICATION STOCK','MODIFICATION PRODUIT','MODIFICATION TAUX','MASQUER PRODUITS','RÉAFFICHER PRODUITS','SAUVEGARDE ÉTAT COMPLET')", (date_cible,)); nb_sensibles=cur.fetchone()[0]
        cur.execute('SELECT heure, operation, reference, description, montant FROM journal WHERE date=? ORDER BY id DESC', (date_cible,)); activites=cur.fetchall()
        date_iso = date_rapport.date().toString('yyyy-MM-dd')
        cur.execute('SELECT horodatage, operation, reference, description, montant FROM audit_events WHERE substr(horodatage,1,10)=? ORDER BY id DESC', (date_iso,)); audits=cur.fetchall()
        conn.close()
        cartes=[('VENTES',formater_nombre(nb_ventes)),('CHIFFRE D’AFFAIRES',formater_nombre(ca_fc)+' FC'),('CA EN DOLLARS',f'{float(ca_usd or 0):.2f} $'),('ARTICLES VENDUS',formater_nombre(articles)),('ACTIVITÉS',formater_nombre(nb_activites)),('ACTIVITÉS SENSIBLES',formater_nombre(nb_sensibles))]
        for i,(titre_carte,valeur) in enumerate(cartes):
            bloc=QLabel(titre_carte+'\n\n'+valeur); bloc.setAlignment(Qt.AlignmentFlag.AlignCenter); bloc.setMinimumHeight(80)
            bloc.setStyleSheet('QLabel { background:#FFFFFF; border:1px solid #CBD5E1; border-radius:8px; padding:10px; font-size:13px; font-weight:bold; }')
            grille.addWidget(bloc,i//3,i%3)
        zone_layout.addLayout(grille)
        zone_layout.addWidget(QLabel('ACTIVITÉS DE LA JOURNÉE'))
        tableau=QTableWidget(); tableau.setColumnCount(5); tableau.setHorizontalHeaderLabels(['HEURE','OPÉRATION','RÉFÉRENCE','DESCRIPTION','MONTANT']); appliquer_tableau_standard(tableau); tableau.setRowCount(len(activites))
        for row,item in enumerate(activites):
            ajouter_ligne_tableau(tableau,row,[item[0],item[1],item[2] or '',item[3] or '',formater_nombre(item[4] or 0)+' FC'])
        tableau.setMinimumHeight(150); zone_layout.addWidget(tableau)
        zone_layout.addWidget(QLabel('TRACE TECHNIQUE / AUDIT'))
        audit=QTableWidget(); audit.setColumnCount(5); audit.setHorizontalHeaderLabels(['HORODATAGE','OPÉRATION','RÉFÉRENCE','DESCRIPTION','MONTANT']); appliquer_tableau_standard(audit); audit.setRowCount(len(audits))
        for row,item in enumerate(audits):
            ajouter_ligne_tableau(audit,row,[item[0],item[1],item[2] or '',item[3] or '',formater_nombre(item[4] or 0)+' FC'])
        audit.setMinimumHeight(130); zone_layout.addWidget(audit)
        zone_layout.addStretch()

    bouton_afficher.clicked.connect(charger_rapport)
    bouton_pdf.clicked.connect(lambda: generer_pdf_rapport_journalier(date_rapport.date().toString('dd/MM/yyyy')))
    charger_rapport()


def afficher_ventes():
    global table_ventes, champ_recherche_vente, panier_vente
    global table_panier_vente, spin_quantite_vente
    global label_total_fc_vente, label_total_usd_vente

    nettoyer_zone()
    panier_vente = []

    contenu.addWidget(creer_titre("VENTES"))

    onglets_ventes = QTabWidget()
    page_nouvelle_vente = QWidget()
    page_historique = QWidget()
    page_dashboard_ventes = QWidget()
    page_rapport_journalier = QWidget()
    page_top_clients = QWidget()
    page_rapports_pdf = QWidget()

    onglets_ventes.addTab(page_nouvelle_vente, "NOUVELLE VENTE")
    onglets_ventes.addTab(page_historique, "HISTORIQUE DES VENTES")
    onglets_ventes.addTab(page_dashboard_ventes, "DASHBOARD")
    onglets_ventes.addTab(page_rapport_journalier, "RAPPORT JOURNALIER")
    onglets_ventes.addTab(page_top_clients, "5 MEILLEURS CLIENTS")
    onglets_ventes.addTab(page_rapports_pdf, "RAPPORTPDF")

    contenu.addWidget(onglets_ventes)
    coloriser_onglets_ventes(onglets_ventes)
    afficher_liste_rapports_pdf(page_rapports_pdf)

    # --------------------------------------------------------
    # NOUVELLE VENTE
    # --------------------------------------------------------

    layout_vente = QVBoxLayout(page_nouvelle_vente)

    # Nom du client associé à la vente.
    ligne_client = QHBoxLayout()
    ligne_client.addWidget(QLabel("Nom du client :"))
    champ_nom_client = QLineEdit()
    champ_nom_client.setPlaceholderText("Saisir le nom du client (facultatif)...")
    ligne_client.addWidget(champ_nom_client)
    layout_vente.addLayout(ligne_client)

    ligne_recherche = QHBoxLayout()
    ligne_recherche.addWidget(QLabel("Recherche :"))

    champ_recherche_vente = QLineEdit()
    champ_recherche_vente.setPlaceholderText("Nom du produit...")

    bouton_rechercher_vente = QPushButton("RECHERCHER")
    ligne_recherche.addWidget(champ_recherche_vente)
    ligne_recherche.addWidget(bouton_rechercher_vente)
    layout_vente.addLayout(ligne_recherche)

    layout_vente.addWidget(QLabel("PRODUITS DISPONIBLES"))

    table_ventes = QTableWidget()
    table_ventes.setColumnCount(6)
    table_ventes.setHorizontalHeaderLabels([
        "ID", "PRODUIT", "PRIX (FC)", "PRIX ($)", "STOCK", "ÉTAT"
    ])
    appliquer_tableau_standard(table_ventes)
    layout_vente.addWidget(table_ventes)

    ligne_ajout = QHBoxLayout()
    ligne_ajout.addWidget(QLabel("Quantité :"))

    spin_quantite_vente = QSpinBox()
    spin_quantite_vente.setMinimum(1)
    spin_quantite_vente.setMaximum(999999)
    spin_quantite_vente.setValue(1)
    ligne_ajout.addWidget(spin_quantite_vente)

    bouton_ajouter_panier = QPushButton("AJOUTER AU PANIER")
    ligne_ajout.addWidget(bouton_ajouter_panier)
    layout_vente.addLayout(ligne_ajout)

    layout_vente.addWidget(QLabel("PANIER"))

    table_panier_vente = QTableWidget()
    table_panier_vente.setColumnCount(6)
    table_panier_vente.setHorizontalHeaderLabels([
        "ID", "PRODUIT", "PRIX (FC)", "QUANTITÉ", "TOTAL (FC)", "TOTAL ($)"
    ])
    appliquer_tableau_standard(table_panier_vente)
    layout_vente.addWidget(table_panier_vente)

    ligne_panier = QHBoxLayout()
    bouton_modifier_quantite = QPushButton("MODIFIER QUANTITÉ")
    bouton_retirer_panier = QPushButton("RETIRER")
    bouton_vider_panier = QPushButton("VIDER LE PANIER")

    ligne_panier.addWidget(bouton_modifier_quantite)
    ligne_panier.addWidget(bouton_retirer_panier)
    ligne_panier.addWidget(bouton_vider_panier)
    layout_vente.addLayout(ligne_panier)

    ligne_totaux = QHBoxLayout()

    label_total_fc_vente = QLabel("TOTAL : 0 FC")
    label_total_fc_vente.setStyleSheet(
        "font-size: 18px; font-weight: bold; padding: 8px;"
    )

    label_total_usd_vente = QLabel("0.00 $")
    label_total_usd_vente.setStyleSheet(
        "font-size: 18px; font-weight: bold; padding: 8px;"
    )

    ligne_totaux.addWidget(label_total_fc_vente)
    ligne_totaux.addWidget(label_total_usd_vente)
    ligne_totaux.addStretch()

    bouton_valider_vente = QPushButton("VALIDER LA VENTE")
    bouton_facture_pdf = QPushButton("FACTURE PDF")
    bouton_valider_vente.setMinimumHeight(40)
    bouton_facture_pdf.setMinimumHeight(40)

    ligne_totaux.addWidget(bouton_valider_vente)
    ligne_totaux.addWidget(bouton_facture_pdf)
    layout_vente.addLayout(ligne_totaux)

    def charger_produits_vente():
        recherche = champ_recherche_vente.text().strip()
        conn = connexion()
        cur = conn.cursor()

        sql = """
            SELECT id, produit, prix_fc, stock
            FROM produits
            WHERE visible = 1 AND stock > 0
        """
        params = []

        if recherche:
            sql += " AND produit LIKE ?"
            params.append("%" + recherche + "%")

        sql += " ORDER BY id ASC"
        cur.execute(sql, params)
        produits = cur.fetchall()
        conn.close()

        table_ventes.clearContents()
        table_ventes.setRowCount(len(produits))

        taux = obtenir_taux()

        for row, produit in enumerate(produits):
            produit_id, nom, prix_fc, stock = produit
            prix_fc = float(prix_fc or 0)
            stock = float(stock or 0)
            prix_usd = prix_fc / taux if taux > 0 else 0

            ajouter_ligne_tableau(table_ventes, row, [
                produit_id,
                nom,
                formater_nombre(prix_fc) + " FC",
                f"{prix_usd:.2f} $",
                formater_nombre(stock),
                calculer_etat(stock),
            ])

    def afficher_panier_vente():
        table_panier_vente.clearContents()
        table_panier_vente.setRowCount(len(panier_vente))

        total_general = 0
        taux = obtenir_taux()

        for row, article in enumerate(panier_vente):
            total_fc = float(article["total_fc"])
            total_general += total_fc
            total_usd = total_fc / taux if taux > 0 else 0

            ajouter_ligne_tableau(table_panier_vente, row, [
                article["id"],
                article["produit"],
                formater_nombre(article["prix_fc"]) + " FC",
                formater_nombre(article["quantite"]),
                formater_nombre(total_fc) + " FC",
                f"{total_usd:.2f} $",
            ])

        total_usd_general = total_general / taux if taux > 0 else 0
        label_total_fc_vente.setText("TOTAL : " + formater_nombre(total_general) + " FC")
        label_total_usd_vente.setText(f"{total_usd_general:.2f} $")

    def ajouter_au_panier():
        row = table_ventes.currentRow()

        if row < 0:
            QMessageBox.warning(fenetre, "VENTE", "Veuillez sélectionner un produit.")
            return

        try:
            produit_id = int(table_ventes.item(row, 0).text())
        except Exception:
            QMessageBox.warning(fenetre, "VENTE", "Produit invalide.")
            return

        quantite = int(spin_quantite_vente.value())

        conn = connexion()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, produit, prix_fc, stock, prix_achat_fc
            FROM produits
            WHERE id = ? AND visible = 1
        """, (produit_id,))
        produit = cur.fetchone()
        conn.close()

        if produit is None:
            QMessageBox.warning(fenetre, "VENTE", "Produit introuvable.")
            return

        nom = produit[1]
        prix_fc = float(produit[2] or 0)
        stock = float(produit[3] or 0)
        prix_achat_fc = float(produit[4] or 0)

        deja = 0
        for article in panier_vente:
            if article["id"] == produit_id:
                deja = article["quantite"]
                break

        if deja + quantite > stock:
            QMessageBox.warning(
                fenetre,
                "STOCK INSUFFISANT",
                "Stock disponible : " + formater_nombre(stock)
            )
            return

        trouve = False
        for article in panier_vente:
            if article["id"] == produit_id:
                article["quantite"] += quantite
                article["total_fc"] = article["prix_fc"] * article["quantite"]
                trouve = True
                break

        if not trouve:
            panier_vente.append({
                "id": produit_id,
                "produit": nom,
                "prix_fc": prix_fc,
                "prix_achat_fc": prix_achat_fc,
                "quantite": quantite,
                "stock": stock,
                "total_fc": prix_fc * quantite,
            })

        afficher_panier_vente()
        spin_quantite_vente.setValue(1)

    def modifier_quantite_panier():
        row = table_panier_vente.currentRow()

        if row < 0:
            QMessageBox.warning(fenetre, "PANIER", "Veuillez sélectionner un article.")
            return

        article = panier_vente[row]
        nouvelle, ok = QInputDialog.getInt(
            fenetre,
            "Modifier quantité",
            "Nouvelle quantité :",
            int(article["quantite"]),
            1,
            int(article["stock"])
        )

        if not ok:
            return

        article["quantite"] = nouvelle
        article["total_fc"] = article["prix_fc"] * nouvelle
        afficher_panier_vente()

    def retirer_article_panier():
        row = table_panier_vente.currentRow()

        if row < 0:
            QMessageBox.warning(fenetre, "PANIER", "Veuillez sélectionner un article.")
            return

        del panier_vente[row]
        afficher_panier_vente()

    def vider_panier_vente():
        if not panier_vente:
            return

        reponse = QMessageBox.question(
            fenetre,
            "VIDER LE PANIER",
            "Voulez-vous vraiment vider le panier ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reponse != QMessageBox.StandardButton.Yes:
            return

        panier_vente.clear()
        afficher_panier_vente()

    # --------------------------------------------------------
    # HISTORIQUE
    # --------------------------------------------------------

    layout_historique = QVBoxLayout(page_historique)
    layout_historique.addWidget(creer_titre("HISTORIQUE DES VENTES", 22))

    bouton_actualiser_historique = QPushButton("ACTUALISER L'HISTORIQUE")
    layout_historique.addWidget(bouton_actualiser_historique)

    table_historique = QTableWidget()
    table_historique.setColumnCount(8)
    table_historique.setHorizontalHeaderLabels([
        "ID", "N° VENTE", "DATE", "HEURE", "CLIENT", "TOTAL (FC)", "TOTAL ($)", "STATUT"
    ])
    appliquer_tableau_standard(table_historique)
    layout_historique.addWidget(table_historique)

    layout_historique.addWidget(QLabel("CONTENU DE LA VENTE"))

    table_details_historique = QTableWidget()
    table_details_historique.setColumnCount(5)
    table_details_historique.setHorizontalHeaderLabels([
        "PRODUIT", "PRIX (FC)", "QUANTITÉ", "TOTAL (FC)", "TOTAL ($)"
    ])
    appliquer_tableau_standard(table_details_historique)
    layout_historique.addWidget(table_details_historique)

    def charger_historique():
        conn = connexion()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, numero_vente, date, heure, nom_client, total_fc, total_usd, statut
            FROM ventes
            ORDER BY id DESC
        """)
        ventes = cur.fetchall()
        conn.close()

        table_historique.clearContents()
        table_historique.setRowCount(len(ventes))

        for row, vente in enumerate(ventes):
            ajouter_ligne_tableau(table_historique, row, [
                vente[0],
                vente[1],
                vente[2],
                vente[3],
                vente[4] or "",
                formater_nombre(vente[5]) + " FC",
                f"{float(vente[6] or 0):.2f} $",
                vente[7],
            ])

        table_details_historique.setRowCount(0)

    def afficher_details_vente():
        row = table_historique.currentRow()

        if row < 0:
            return

        item = table_historique.item(row, 0)
        if item is None:
            return

        vente_id = int(item.text())

        conn = connexion()
        cur = conn.cursor()
        cur.execute("""
            SELECT produit, prix_fc, quantite, total_fc
            FROM vente_details
            WHERE vente_id = ?
            ORDER BY id
        """, (vente_id,))
        details = cur.fetchall()
        conn.close()

        table_details_historique.clearContents()
        table_details_historique.setRowCount(len(details))

        taux = obtenir_taux()

        for row, detail in enumerate(details):
            total_fc = float(detail[3] or 0)
            total_usd = total_fc / taux if taux > 0 else 0
            ajouter_ligne_tableau(table_details_historique, row, [
                detail[0],
                formater_nombre(detail[1]) + " FC",
                formater_nombre(detail[2]),
                formater_nombre(total_fc) + " FC",
                f"{total_usd:.2f} $",
            ])

    def facture_pdf_selectionnee():
        row = table_historique.currentRow()
        if row < 0:
            QMessageBox.warning(
                fenetre,
                "FACTURE PDF",
                "Sélectionnez d'abord une vente dans l'historique."
            )
            return

        item = table_historique.item(row, 0)
        if item is None:
            return

        facture_pdf_vente(int(item.text()))

    def valider_vente():
        if not panier_vente:
            QMessageBox.warning(fenetre, "VENTE", "Le panier est vide.")
            return

        confirmation = QMessageBox.question(
            fenetre,
            "VALIDER LA VENTE",
            "Voulez-vous enregistrer cette vente ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirmation != QMessageBox.StandardButton.Yes:
            return

        conn = connexion()

        try:
            cur = conn.cursor()

            for article in panier_vente:
                cur.execute("""
                    SELECT produit, prix_fc, stock, prix_achat_fc
                    FROM produits
                    WHERE id = ? AND visible = 1
                """, (article["id"],))
                produit = cur.fetchone()

                if produit is None:
                    raise Exception("Le produit " + article["produit"] + " n'existe plus.")

                stock_reel = float(produit[2] or 0)

                if article["quantite"] > stock_reel:
                    raise Exception(
                        "Stock insuffisant pour : " + article["produit"] +
                        "\nStock disponible : " + formater_nombre(stock_reel)
                    )

            total_fc = sum(article["total_fc"] for article in panier_vente)
            taux = obtenir_taux()
            total_usd = total_fc / taux if taux > 0 else 0

            dt = maintenant()
            date_vente = dt.strftime("%d/%m/%Y")
            heure_vente = dt.strftime("%H:%M:%S")

            # Utilisation d'un numéro temporaire unique.
            numero_temp = "TEMP-" + dt.strftime("%Y%m%d%H%M%S%f")

            nom_client = champ_nom_client.text().strip()

            cur.execute("""
                INSERT INTO ventes
                (numero_vente, date, heure, nom_client, total_fc, total_usd, statut)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                numero_temp,
                date_vente,
                heure_vente,
                nom_client,
                total_fc,
                total_usd,
                "VALIDEE",
            ))

            vente_id = cur.lastrowid

            numero_vente = (
                "FAC-" + dt.strftime("%Y%m%d") + "-" + f"{vente_id:04d}"
            )

            cur.execute(
                "UPDATE ventes SET numero_vente = ? WHERE id = ?",
                (numero_vente, vente_id)
            )

            for article in panier_vente:
                cur.execute("""
                    INSERT INTO vente_details
                    (vente_id, produit_id, produit, prix_fc, quantite, total_fc, prix_achat_fc)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    vente_id,
                    article["id"],
                    article["produit"],
                    article["prix_fc"],
                    article["quantite"],
                    article["total_fc"],
                    article["prix_achat_fc"],
                ))

                cur.execute("""
                    UPDATE produits
                    SET stock = stock - ?
                    WHERE id = ?
                """, (article["quantite"], article["id"]))

            enregistrer_audit_conn(
                conn,
                "VENTE",
                numero_vente,
                "Vente enregistrée",
                total_fc
            )

            conn.execute("""
                INSERT INTO journal
                (date, heure, operation, reference, description, montant)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                date_vente,
                heure_vente,
                "VENTE",
                numero_vente,
                "Vente enregistrée",
                total_fc,
            ))

            conn.commit()

        except Exception as erreur:
            conn.rollback()
            conn.close()
            QMessageBox.critical(
                fenetre,
                "ERREUR",
                "La vente n'a pas été enregistrée.\n\n" + str(erreur)
            )
            return

        conn.close()

        QMessageBox.information(
            fenetre,
            "VENTE ENREGISTRÉE",
            "Vente enregistrée avec succès.\n\n"
            "Numéro : " + numero_vente + "\n"
            "Total : " + formater_nombre(total_fc) + " FC"
        )

        panier_vente.clear()
        champ_nom_client.clear()
        afficher_panier_vente()
        charger_produits_vente()
        charger_historique()
        construire_dashboard_ventes(page_dashboard_ventes)
        onglets_ventes.setCurrentWidget(page_historique)

    bouton_rechercher_vente.clicked.connect(charger_produits_vente)
    champ_recherche_vente.returnPressed.connect(charger_produits_vente)
    bouton_ajouter_panier.clicked.connect(ajouter_au_panier)
    bouton_modifier_quantite.clicked.connect(modifier_quantite_panier)
    bouton_retirer_panier.clicked.connect(retirer_article_panier)
    bouton_vider_panier.clicked.connect(vider_panier_vente)
    bouton_valider_vente.clicked.connect(valider_vente)
    bouton_facture_pdf.clicked.connect(facture_pdf_selectionnee)
    table_historique.cellClicked.connect(
        lambda row, column: afficher_details_vente()
    )
    bouton_actualiser_historique.clicked.connect(charger_historique)

    construire_dashboard_ventes(page_dashboard_ventes)
    afficher_rapport_journalier_ventes(page_rapport_journalier)

    # --------------------------------------------------------
    # 5 MEILLEURS CLIENTS
    # --------------------------------------------------------
    layout_top_clients = QVBoxLayout(page_top_clients)
    layout_top_clients.addWidget(creer_titre("5 MEILLEURS CLIENTS", 24))
    layout_top_clients.addWidget(QLabel(
        "Classement selon le montant total versé, puis le nombre de factures."
    ))

    table_top_clients = QTableWidget()
    table_top_clients.setColumnCount(5)
    table_top_clients.setHorizontalHeaderLabels([
        "RANG", "CLIENT", "MONTANT TOTAL VERSÉ (FC)",
        "NOMBRE DE FACTURES", "N° DERNIÈRE FACTURE"
    ])
    appliquer_tableau_standard(table_top_clients)
    layout_top_clients.addWidget(table_top_clients)

    conn_top = connexion()
    cur_top = conn_top.cursor()
    cur_top.execute("""
        SELECT
            COALESCE(NULLIF(TRIM(nom_client), ''), 'Client comptant') AS client,
            COALESCE(SUM(total_fc), 0) AS montant,
            COUNT(*) AS nb_factures,
            MAX(numero_vente) AS derniere_facture
        FROM ventes
        GROUP BY COALESCE(NULLIF(TRIM(nom_client), ''), 'Client comptant')
        ORDER BY montant DESC, nb_factures DESC, derniere_facture DESC
        LIMIT 5
    """)
    top_clients = cur_top.fetchall()
    conn_top.close()

    table_top_clients.setRowCount(len(top_clients))
    for row, item in enumerate(top_clients):
        ajouter_ligne_tableau(table_top_clients, row, [
            row + 1,
            item[0],
            formater_nombre(item[1] or 0) + " FC",
            item[2],
            item[3] or "—",
        ])

    if not top_clients:
        table_top_clients.setRowCount(1)
        ajouter_ligne_tableau(table_top_clients, 0, [
            "—", "Aucun client enregistré", "0 FC", 0, "—"
        ])

    layout_top_clients.addStretch()

    charger_produits_vente()
    charger_historique()


# ============================================================
# GRAPHIQUE STATISTIQUE NATIF (fonctionne hors connexion)
# ============================================================
class GraphiqueVentesBenefices(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.setMinimumHeight(270)
        self.setMinimumWidth(420)

    def definir_donnees(self, points):
        self.points = list(points or [])[-12:]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -34)
        painter.fillRect(self.rect(), QBrush(QColor("#F8FAFC")))
        painter.setPen(QPen(QColor("#E2E8F0"), 1))
        for i in range(5):
            y = rect.top() + i * rect.height() / 4
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        painter.setPen(QPen(QColor("#415A70"), 1))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        painter.drawText(20, 18, "ÉVOLUTION DES VENTES ET DES BÉNÉFICES (FC)")
        if not self.points:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Aucune vente enregistrée")
            painter.end()
            return
        max_val = max([max(float(a or 0), float(b or 0)) for _, a, b in self.points] + [1])
        n = len(self.points)
        step = rect.width() / max(n, 1)
        base_y = rect.bottom()
        for i, (jour, ca, benef) in enumerate(self.points):
            x = rect.left() + i * step + step * 0.18
            bw = max(3, step * 0.27)
            h_ca = rect.height() * max(0, float(ca or 0)) / max_val
            h_b = rect.height() * max(0, float(benef or 0)) / max_val
            painter.fillRect(int(x), int(base_y-h_ca), int(bw), int(h_ca), QBrush(QColor("#2563EB")))
            painter.fillRect(int(x+bw+2), int(base_y-h_b), int(bw), int(h_b), QBrush(QColor("#16A34A")))
            painter.setPen(QPen(Qt.GlobalColor.darkGray, 1))
            painter.drawText(int(x-step*0.1), int(base_y+16), max(1, int(step*1.1)), 14,
                             Qt.AlignmentFlag.AlignHCenter, str(jour)[0:5])
        # Légende
        painter.fillRect(22, self.height()-18, 10, 10, QBrush(QColor("#2563EB")))
        painter.drawText(36, self.height()-9, "Ventes / CA")
        painter.fillRect(145, self.height()-18, 10, 10, QBrush(QColor("#16A34A")))
        painter.drawText(159, self.height()-9, "Bénéfice")
        painter.end()


# ============================================================
# STATISTIQUES
# ============================================================

def afficher_statistiques():
    nettoyer_zone()
    contenu.addWidget(creer_titre("STATISTIQUES", 30))

    ligne_filtres = QHBoxLayout()
    ligne_filtres.addWidget(QLabel("Date :"))

    date_stat = QDateEdit()
    date_stat.setCalendarPopup(True)
    date_stat.setDate(QDate.currentDate())
    ligne_filtres.addWidget(date_stat)

    bouton_actualiser = QPushButton("ACTUALISER")
    ligne_filtres.addWidget(bouton_actualiser)
    ligne_filtres.addStretch()

    contenu.addLayout(ligne_filtres)

    tableau = QTableWidget()
    tableau.setColumnCount(4)
    tableau.setHorizontalHeaderLabels([
        "DATE", "CHIFFRE D'AFFAIRES (FC)", "BÉNÉFICE (FC)", "MARGE (%)"
    ])
    appliquer_tableau_standard(tableau)
    contenu.addWidget(tableau)

    label_ca = QLabel("CHIFFRE D'AFFAIRES : 0 FC")
    label_benefice = QLabel("BÉNÉFICE : 0 FC")
    label_ca.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px;")
    label_benefice.setStyleSheet("font-size: 18px; font-weight: bold; padding: 5px;")
    contenu.addWidget(label_ca)
    contenu.addWidget(label_benefice)

    contenu.addWidget(QLabel("📊 ÉVOLUTION DES VENTES ET DES BÉNÉFICES"))
    graphique = GraphiqueVentesBenefices()
    contenu.addWidget(graphique)

    graphique_table = QTableWidget()
    graphique_table.setColumnCount(3)
    graphique_table.setHorizontalHeaderLabels(["DATE", "VENTES / CA (FC)", "BÉNÉFICE (FC)"])
    appliquer_tableau_standard(graphique_table)
    graphique_table.setMaximumHeight(190)
    contenu.addWidget(graphique_table)

    def charger():
        qdate = date_stat.date()
        date_cible = qdate.toString("dd/MM/yyyy")

        conn = connexion()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                COALESCE(SUM(total_fc), 0),
                COUNT(*)
            FROM ventes
            WHERE date = ?
        """, (date_cible,))
        ca, nb = cur.fetchone()

        cur.execute("""
            SELECT COALESCE(SUM(
                (vd.prix_fc - vd.prix_achat_fc) * vd.quantite
            ), 0)
            FROM vente_details vd
            JOIN ventes v ON v.id = vd.vente_id
            WHERE v.date = ?
        """, (date_cible,))
        benefice = cur.fetchone()[0]

        cur.execute("""
            SELECT ventes_jour.date, ventes_jour.ca, COALESCE(benefices_jour.benefice, 0)
            FROM (
                SELECT date, COALESCE(SUM(total_fc), 0) AS ca
                FROM ventes GROUP BY date
            ) AS ventes_jour
            LEFT JOIN (
                SELECT v.date,
                       COALESCE(SUM((vd.prix_fc - vd.prix_achat_fc) * vd.quantite), 0) AS benefice
                FROM ventes v
                JOIN vente_details vd ON vd.vente_id = v.id
                GROUP BY v.date
            ) AS benefices_jour ON benefices_jour.date = ventes_jour.date
            ORDER BY substr(ventes_jour.date, 7, 4),
                     substr(ventes_jour.date, 4, 2), substr(ventes_jour.date, 1, 2)
        """)
        evolution = cur.fetchall()
        conn.close()

        marge = (float(benefice or 0) / float(ca or 1) * 100) if ca else 0

        tableau.setRowCount(1)
        ajouter_ligne_tableau(tableau, 0, [
            date_cible,
            formater_nombre(ca) + " FC",
            formater_nombre(benefice) + " FC",
            f"{marge:.2f} %",
        ])

        label_ca.setText(
            f"CHIFFRE D'AFFAIRES : {formater_nombre(ca)} FC  |  VENTES : {nb}"
        )
        label_benefice.setText(
            f"BÉNÉFICE : {formater_nombre(benefice)} FC"
        )

        graphique.definir_donnees(evolution)
        graphique_table.setRowCount(len(evolution))
        for row, item in enumerate(evolution):
            ajouter_ligne_tableau(
                graphique_table, row,
                [item[0], formater_nombre(item[1]) + " FC", formater_nombre(item[2]) + " FC"]
            )

    bouton_actualiser.clicked.connect(charger)
    charger()


# ============================================================
# JOURNAL
# ============================================================

def afficher_journal():
    nettoyer_zone()
    contenu.addWidget(creer_titre("JOURNAL", 30))

    ligne = QHBoxLayout()
    champ = QLineEdit()
    champ.setPlaceholderText("Rechercher une opération, référence ou description...")
    bouton = QPushButton("RECHERCHER")
    ligne.addWidget(champ)
    ligne.addWidget(bouton)
    contenu.addLayout(ligne)

    tableau = QTableWidget()
    tableau.setColumnCount(7)
    tableau.setHorizontalHeaderLabels([
        "ID", "DATE", "HEURE", "OPÉRATION",
        "RÉFÉRENCE", "DESCRIPTION", "MONTANT (FC)"
    ])
    appliquer_tableau_standard(tableau)
    contenu.addWidget(tableau)

    def charger():
        recherche = champ.text().strip()
        conn = connexion()
        cur = conn.cursor()

        sql = """
            SELECT id, date, heure, operation, reference, description, montant
            FROM journal
        """
        params = []

        if recherche:
            sql += """
                WHERE operation LIKE ?
                OR reference LIKE ?
                OR description LIKE ?
            """
            valeur = "%" + recherche + "%"
            params = [valeur, valeur, valeur]

        sql += " ORDER BY id DESC"
        cur.execute(sql, params)
        lignes = cur.fetchall()
        conn.close()

        tableau.setRowCount(len(lignes))
        for row, ligne in enumerate(lignes):
            ajouter_ligne_tableau(tableau, row, [
                ligne[0],
                ligne[1],
                ligne[2],
                ligne[3],
                ligne[4] or "",
                ligne[5] or "",
                formater_nombre(ligne[6]) + " FC",
            ])

    bouton.clicked.connect(charger)
    champ.returnPressed.connect(charger)
    charger()



# ============================================================
# PDF — FICHE PROFESSIONNELLE D'UN CRÉDIT
# ============================================================

def credit_pdf(credit_id):
    """Génère une fiche PDF professionnelle du crédit sélectionné."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            Image, KeepTogether
        )
    except ImportError:
        QMessageBox.warning(
            fenetre,
            "PDF CRÉDIT",
            "Le module ReportLab n'est pas installé.\n\n"
            "Installez-le avec :\n"
            "pip install reportlab"
        )
        return

    conn = connexion()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, reference, client, numero_client, date, echeance,
               montant_total, montant_paye, solde, statut
        FROM credits
        WHERE id=?
    """, (credit_id,))
    credit = cur.fetchone()

    if credit is None:
        conn.close()
        QMessageBox.warning(fenetre, "PDF CRÉDIT", "Crédit introuvable.")
        return

    cur.execute("""
        SELECT id, date, heure, montant, mode_paiement, observation
        FROM credit_paiements
        WHERE credit_id=?
        ORDER BY id
    """, (credit_id,))
    paiements = cur.fetchall()
    conn.close()

    (
        identifiant, reference, client, numero_client, date_credit,
        echeance, montant_total, montant_paye, solde, statut
    ) = credit

    RAPPORTS_PDF_DIR.mkdir(parents=True, exist_ok=True)
    nom_fichier = (
        RAPPORTS_PDF_DIR /
        f"Credit_{reference}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

    styles = getSampleStyleSheet()
    style_titre = ParagraphStyle(
        "CreditTitre", parent=styles["Title"],
        fontName="Helvetica-Bold", fontSize=19, leading=22,
        textColor=colors.HexColor("#17324D"), alignment=TA_LEFT,
        spaceAfter=3*mm
    )
    style_sous_titre = ParagraphStyle(
        "CreditSousTitre", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9.5, leading=12,
        textColor=colors.HexColor("#60758A")
    )
    style_section = ParagraphStyle(
        "CreditSection", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=11, leading=14,
        textColor=colors.HexColor("#FFFFFF"), backColor=colors.HexColor("#1D4ED8"),
        borderPadding=(5, 7, 5, 7), spaceBefore=4*mm, spaceAfter=3*mm
    )
    style_normal = ParagraphStyle(
        "CreditNormal", parent=styles["Normal"],
        fontName="Helvetica", fontSize=9.5, leading=13,
        textColor=colors.HexColor("#1F2937")
    )
    style_small = ParagraphStyle(
        "CreditSmall", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8, leading=10,
        textColor=colors.HexColor("#64748B")
    )
    style_total = ParagraphStyle(
        "CreditTotal", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=11, leading=14,
        textColor=colors.HexColor("#17324D")
    )

    def P(value, style=style_normal):
        return Paragraph(str(value if value is not None else ""), style)

    doc = SimpleDocTemplate(
        str(nom_fichier),
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm,
        title=f"Fiche crédit {reference}",
        author="BILLY-eLBERT STOCK"
    )

    elements = []

    # En-tête avec logo si disponible.
    entete_gauche = []
    if LOGO_PATH.exists():
        try:
            img = Image(str(LOGO_PATH), width=23*mm, height=23*mm)
            entete_gauche.append(img)
        except Exception:
            pass

    bloc_titre = [
        P(__import__("xml.sax.saxutils", fromlist=["escape"]).escape(obtenir_message_accueil_pdf()), style_titre),
        P("FICHE DE GESTION DE CRÉDIT", ParagraphStyle(
            "CreditLabel", parent=style_sous_titre,
            fontName="Helvetica-Bold", fontSize=10,
            textColor=colors.HexColor("#1D4ED8")
        )),
        P(
            f"Référence : <b>{reference}</b> &nbsp;&nbsp; "
            f"|&nbsp;&nbsp; Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}",
            style_sous_titre
        )
    ]

    if entete_gauche:
        header_table = Table(
            [[entete_gauche[0], bloc_titre]],
            colWidths=[28*mm, 147*mm]
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 0),
            ("RIGHTPADDING", (0,0), (-1,-1), 5),
            ("TOPPADDING", (0,0), (-1,-1), 0),
            ("BOTTOMPADDING", (0,0), (-1,-1), 0),
        ]))
        elements.append(header_table)
    else:
        elements.extend(bloc_titre)

    elements.append(Spacer(1, 5*mm))

    # Informations client.
    elements.append(P("IDENTIFICATION DU CLIENT", style_section))
    info = [
        [P("<b>CLIENT</b>"), P(client or "—"),
         P("<b>NUMÉRO DU CLIENT</b>"), P(numero_client or "—")],
        [P("<b>DATE DU CRÉDIT</b>"), P(date_credit or "—"),
         P("<b>ÉCHÉANCE</b>"), P(echeance or "—")],
        [P("<b>RÉFÉRENCE</b>"), P(reference),
         P("<b>ÉTAT</b>"), P(f"<b>{statut}</b>")],
    ]
    info_table = Table(info, colWidths=[35*mm, 57*mm, 40*mm, 43*mm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#F1F5F9")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#F1F5F9")),
        ("BOX", (0,0), (-1,-1), 0.7, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D9E1EA")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    elements.append(info_table)

    # Résumé financier.
    elements.append(P("SITUATION FINANCIÈRE", style_section))
    total = float(montant_total or 0)
    paye = float(montant_paye or 0)
    reste = float(solde or 0)
    taux = obtenir_taux()
    resume = [
        [P("<b>TOTAL CRÉDIT</b>"), P(f"{formater_nombre(total)} FC"),
         P("<b>TOTAL PAYÉ</b>"), P(f"{formater_nombre(paye)} FC")],
        [P("<b>RESTE À RÉCUPÉRER</b>"), P(f"<b>{formater_nombre(reste)} FC</b>"),
         P("<b>ÉTAT</b>"), P(f"<b>{statut}</b>")],
    ]
    resume_table = Table(resume, colWidths=[40*mm, 48*mm, 40*mm, 47*mm])
    resume_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.white),
        ("BACKGROUND", (0,1), (1,1), colors.HexColor("#FFF7ED") if reste > 0 else colors.HexColor("#ECFDF5")),
        ("BOX", (0,0), (-1,-1), 0.8, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0,0), (-1,-1), 0.4, colors.HexColor("#D9E1EA")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("ALIGN", (3,0), (3,-1), "RIGHT"),
        ("LEFTPADDING", (0,0), (-1,-1), 7),
        ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    elements.append(resume_table)

    # Historique des paiements.
    elements.append(P("HISTORIQUE DES PAIEMENTS", style_section))
    paiement_rows = [[
        P("<b>ID</b>"), P("<b>DATE</b>"), P("<b>HEURE</b>"),
        P("<b>MONTANT</b>"), P("<b>MODE</b>"), P("<b>OBSERVATION</b>")
    ]]
    for paiement in paiements:
        paiement_rows.append([
            P(paiement[0]), P(paiement[1]), P(paiement[2]),
            P(f"{formater_nombre(paiement[3])} FC"),
            P(paiement[4] or "—"),
            P(paiement[5] or "—")
        ])

    if len(paiement_rows) == 1:
        paiement_rows.append([
            P("—"), P("—"), P("—"), P("0 FC"), P("—"), P("Aucun paiement enregistré")
        ])

    paiement_table = Table(
        paiement_rows,
        colWidths=[12*mm, 25*mm, 22*mm, 32*mm, 35*mm, 49*mm],
        repeatRows=1
    )
    paiement_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#334155")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("BOX", (0,0), (-1,-1), 0.7, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0,0), (-1,-1), 0.35, colors.HexColor("#D9E1EA")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1),
         [colors.white, colors.HexColor("#F8FAFC")]),
        ("ALIGN", (0,0), (0,-1), "CENTER"),
        ("ALIGN", (3,1), (3,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elements.append(paiement_table)

    elements.append(Spacer(1, 7*mm))
    elements.append(P(
        "Document généré automatiquement par " + __import__("xml.sax.saxutils", fromlist=["escape"]).escape(obtenir_message_accueil_pdf()) + ". "
        "Ce document constitue un relevé de situation du crédit à la date de génération.",
        style_small
    ))
    elements.append(Spacer(1, 12*mm))

    signature = Table([
        [P("<b>RESPONSABLE / CAISSE</b>"), P("<b>CLIENT</b>")],
        [P("Signature : __________________________"), P("Signature : __________________________")],
    ], colWidths=[87.5*mm, 87.5*mm])
    signature.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("TEXTCOLOR", (0,0), (-1,-1), colors.HexColor("#475569")),
    ]))
    elements.append(signature)

    def pied_de_page(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas_obj.line(15*mm, 11*mm, 195*mm, 11*mm)
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.setFillColor(colors.HexColor("#64748B"))
        canvas_obj.drawString(
            15*mm, 7*mm,
            obtenir_message_accueil_pdf()
        )
        canvas_obj.drawRightString(
            195*mm, 7*mm,
            f"Page {doc_obj.page}"
        )
        canvas_obj.restoreState()

    try:
        doc.build(
            elements,
            onFirstPage=pied_de_page,
            onLaterPages=pied_de_page
        )
    except Exception as exc:
        QMessageBox.critical(
            fenetre,
            "PDF CRÉDIT",
            "Impossible de générer le PDF :\n\n" + str(exc)
        )
        return

    QMessageBox.information(
        fenetre,
        "PDF CRÉDIT",
        f"Fiche PDF générée avec succès.\n\n"
        f"Référence : {reference}\n"
        f"Fichier :\n{nom_fichier}"
    )

    try:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(nom_fichier)))
    except Exception:
        pass


# ============================================================
# GESTION DES CRÉDITS
# ============================================================

def afficher_credits():
    """Gestion complète des ventes à crédit, corrections, remboursements et PDF."""
    nettoyer_zone()
    contenu.addWidget(creer_titre("💳 GESTION DES CRÉDITS", 30))

    # --------------------------------------------------------
    # INDICATEURS
    # --------------------------------------------------------
    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*),
            COALESCE(SUM(montant_total), 0),
            COALESCE(SUM(montant_paye), 0),
            COALESCE(SUM(solde), 0),
            COALESCE(SUM(CASE WHEN solde > 0 AND echeance IS NOT NULL
                              AND echeance <> ''
                              AND substr(echeance,7,4)||substr(echeance,4,2)||substr(echeance,1,2)
                                  < strftime('%Y%m%d','now')
                              THEN 1 ELSE 0 END), 0)
        FROM credits
    """)
    stats = cur.fetchone()
    conn.close()

    nb_credits = int(stats[0] or 0)
    total_credit = float(stats[1] or 0)
    total_paye = float(stats[2] or 0)
    total_restant = float(stats[3] or 0)
    nb_retard = int(stats[4] or 0)

    grille = QGridLayout()
    cartes = [
        ("📄 CRÉDITS", formater_nombre(nb_credits), 0),
        ("💰 TOTAL CRÉDITÉ", formater_nombre(total_credit) + " FC", 1),
        ("✅ TOTAL PAYÉ", formater_nombre(total_paye) + " FC", 2),
        ("⚠️ RESTE À RÉCUPÉRER", formater_nombre(total_restant) + " FC", 3),
        ("🔴 CRÉDITS EN RETARD", str(nb_retard), 4),
    ]
    for i, (nom, valeur, index) in enumerate(cartes):
        grille.addWidget(creer_carte_dashboard(nom, valeur, index), i // 3, i % 3)
    contenu.addLayout(grille)

    # --------------------------------------------------------
    # NOUVEAU CRÉDIT
    # --------------------------------------------------------
    groupe_nouveau = QGroupBox("NOUVEAU CRÉDIT")
    form = QGridLayout(groupe_nouveau)

    champ_client = QLineEdit()
    champ_client.setPlaceholderText("Nom du client")

    champ_numero_client = QLineEdit()
    champ_numero_client.setPlaceholderText("Numéro du client / téléphone")
    champ_numero_client.setMaxLength(50)

    champ_montant = QDoubleSpinBox()
    champ_montant.setRange(0, 999999999999)
    champ_montant.setDecimals(2)
    champ_montant.setSuffix(" FC")
    champ_montant.setSingleStep(1000)

    champ_paye = QDoubleSpinBox()
    champ_paye.setRange(0, 999999999999)
    champ_paye.setDecimals(2)
    champ_paye.setSuffix(" FC")
    champ_paye.setSingleStep(1000)

    champ_echeance = QDateEdit(QDate.currentDate())
    champ_echeance.setCalendarPopup(True)
    champ_echeance.setDisplayFormat("dd/MM/yyyy")

    form.addWidget(QLabel("CLIENT"), 0, 0)
    form.addWidget(champ_client, 0, 1)
    form.addWidget(QLabel("NUMÉRO DU CLIENT"), 0, 2)
    form.addWidget(champ_numero_client, 0, 3)

    form.addWidget(QLabel("MONTANT TOTAL"), 1, 0)
    form.addWidget(champ_montant, 1, 1)
    form.addWidget(QLabel("MONTANT DÉJÀ PAYÉ"), 1, 2)
    form.addWidget(champ_paye, 1, 3)

    form.addWidget(QLabel("ÉCHÉANCE"), 2, 0)
    form.addWidget(champ_echeance, 2, 1)

    bouton_creer = QPushButton("➕ ENREGISTRER LE CRÉDIT")
    form.addWidget(bouton_creer, 3, 0, 1, 4)
    contenu.addWidget(groupe_nouveau)

    # --------------------------------------------------------
    # HISTORIQUE DES CRÉDITS
    # --------------------------------------------------------
    barre = QHBoxLayout()
    recherche = QLineEdit()
    recherche.setPlaceholderText(
        "Rechercher un client, un numéro, une référence ou un état..."
    )

    bouton_actualiser = QPushButton("🔄 ACTUALISER")
    bouton_modifier = QPushButton("✏️ MODIFIER")
    bouton_paiement = QPushButton("💵 ENREGISTRER UN REMBOURSEMENT")
    bouton_details = QPushButton("📋 HISTORIQUE DES PAIEMENTS")
    bouton_pdf = QPushButton("📄 PDF DU CRÉDIT")

    barre.addWidget(recherche, 1)
    barre.addWidget(bouton_actualiser)
    barre.addWidget(bouton_modifier)
    barre.addWidget(bouton_paiement)
    barre.addWidget(bouton_details)
    barre.addWidget(bouton_pdf)
    contenu.addLayout(barre)

    table_credits = QTableWidget()
    table_credits.setColumnCount(10)
    table_credits.setHorizontalHeaderLabels([
        "ID", "RÉFÉRENCE", "CLIENT", "N° CLIENT", "DATE", "ÉCHÉANCE",
        "TOTAL", "PAYÉ", "SOLDE", "ÉTAT"
    ])
    appliquer_tableau_standard(table_credits)
    table_credits.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table_credits.setAlternatingRowColors(True)
    table_credits.setStyleSheet("""
        QTableWidget { background:#FFFFFF; alternate-background-color:#F1F5F9; color:#1F2937; }
        QTableWidget::item { background:#FFFFFF; color:#1F2937; padding:7px; }
        QTableWidget::item:alternate { background:#F1F5F9; color:#1F2937; }
        QTableWidget::item:selected, QTableWidget::item:selected:alternate {
            background:#1D4ED8; color:#FFFFFF; font-weight:800;
        }
    """)
    contenu.addWidget(table_credits)

    def etat_credit(echeance, solde):
        solde = float(solde or 0)
        if solde <= 0.000001:
            return "PAYÉ"
        if echeance:
            try:
                d = datetime.strptime(str(echeance), "%d/%m/%Y").date()
                if d < date.today():
                    return "EN RETARD"
            except Exception:
                pass
        return "EN COURS"

    def charger_credits():
        terme = recherche.text().strip()
        conn = connexion()
        cur = conn.cursor()
        sql = """
            SELECT id, reference, client, numero_client, date, echeance,
                   montant_total, montant_paye, solde, statut
            FROM credits
        """
        params = []
        if terme:
            valeur = "%" + terme + "%"
            sql += """
                WHERE client LIKE ?
                   OR numero_client LIKE ?
                   OR reference LIKE ?
                   OR statut LIKE ?
            """
            params = [valeur, valeur, valeur, valeur]

        sql += " ORDER BY id DESC"
        cur.execute(sql, params)
        lignes = cur.fetchall()

        for ligne in lignes:
            statut_calcule = etat_credit(ligne[5], ligne[8])
            if statut_calcule != ligne[9]:
                cur.execute(
                    "UPDATE credits SET statut=? WHERE id=?",
                    (statut_calcule, ligne[0])
                )
        conn.commit()
        conn.close()

        table_credits.setRowCount(len(lignes))
        for row, ligne in enumerate(lignes):
            statut = etat_credit(ligne[5], ligne[8])
            ajouter_ligne_tableau(table_credits, row, [
                ligne[0],
                ligne[1],
                ligne[2],
                ligne[3] or "—",
                ligne[4],
                ligne[5] or "—",
                formater_nombre(ligne[6]) + " FC",
                formater_nombre(ligne[7]) + " FC",
                formater_nombre(ligne[8]) + " FC",
                statut,
            ])

    def vider_formulaire_credit():
        champ_client.clear()
        champ_numero_client.clear()
        champ_montant.setValue(0)
        champ_paye.setValue(0)
        champ_echeance.setDate(QDate.currentDate())

    def creer_credit():
        client = champ_client.text().strip()
        numero_client = champ_numero_client.text().strip()
        montant = float(champ_montant.value() or 0)
        paye = float(champ_paye.value() or 0)
        echeance = champ_echeance.date().toString("dd/MM/yyyy")

        if not client:
            QMessageBox.warning(
                fenetre, "CRÉDIT",
                "Veuillez renseigner le nom du client."
            )
            return

        if montant <= 0:
            QMessageBox.warning(
                fenetre, "CRÉDIT",
                "Le montant du crédit doit être supérieur à zéro."
            )
            return

        if paye < 0 or paye > montant:
            QMessageBox.warning(
                fenetre, "CRÉDIT",
                "Le montant payé doit être compris entre 0 et le montant total."
            )
            return

        solde = montant - paye
        statut = etat_credit(echeance, solde)
        dt = maintenant()

        conn = connexion()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM credits")
            prochain = int(cur.fetchone()[0])
            reference = (
                "CRD-" + dt.strftime("%Y%m%d") + "-" + f"{prochain:04d}"
            )

            cur.execute("""
                INSERT INTO credits
                (reference, client, date, echeance, montant_total,
                 montant_paye, solde, statut, observation, numero_client)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reference,
                client,
                dt.strftime("%d/%m/%Y"),
                echeance,
                montant,
                paye,
                solde,
                statut,
                "",
                numero_client
            ))

            credit_id = cur.lastrowid

            if paye > 0:
                cur.execute("""
                    INSERT INTO credit_paiements
                    (credit_id, date, heure, montant, mode_paiement, observation)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    credit_id,
                    dt.strftime("%d/%m/%Y"),
                    dt.strftime("%H:%M:%S"),
                    paye,
                    "VERSEMENT INITIAL",
                    ""
                ))

            enregistrer_audit_conn(
                conn, "CRÉDIT", reference,
                "Crédit client enregistré", montant
            )

            conn.execute("""
                INSERT INTO journal
                (date, heure, operation, reference, description, montant)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                dt.strftime("%d/%m/%Y"),
                dt.strftime("%H:%M:%S"),
                "CRÉDIT",
                reference,
                "Crédit client enregistré",
                montant
            ))

            conn.commit()

        except Exception as exc:
            conn.rollback()
            conn.close()
            QMessageBox.critical(
                fenetre,
                "CRÉDIT",
                "Impossible d'enregistrer le crédit :\n\n" + str(exc)
            )
            return

        conn.close()

        QMessageBox.information(
            fenetre,
            "CRÉDIT ENREGISTRÉ",
            f"Crédit enregistré avec succès.\n\n"
            f"Référence : {reference}\n"
            f"Client : {client}\n"
            f"Solde restant : {formater_nombre(solde)} FC"
        )

        vider_formulaire_credit()
        charger_credits()

    def obtenir_credit_selectionne():
        row = table_credits.currentRow()

        if row < 0:
            QMessageBox.warning(
                fenetre,
                "CRÉDIT",
                "Veuillez sélectionner un crédit."
            )
            return None

        item = table_credits.item(row, 0)
        if item is None:
            return None

        try:
            credit_id = int(item.text())
        except Exception:
            QMessageBox.warning(
                fenetre,
                "CRÉDIT",
                "Identifiant du crédit invalide."
            )
            return None

        conn = connexion()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, reference, client, numero_client, date, echeance,
                   montant_total, montant_paye, solde, statut
            FROM credits
            WHERE id=?
        """, (credit_id,))
        credit = cur.fetchone()
        conn.close()
        return credit

    def modifier_credit():
        credit = obtenir_credit_selectionne()
        if credit is None:
            return

        (
            credit_id, reference, client, numero_client,
            date_credit, echeance, total, paye, solde, statut
        ) = credit

        dlg = QDialog(fenetre)
        dlg.setWindowTitle(f"✏️ MODIFIER LE CRÉDIT — {reference}")
        dlg.resize(560, 360)

        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(
            f"<b>Référence :</b> {reference}<br>"
            f"<b>Date :</b> {date_credit}"
        ))

        form_mod = QGridLayout()

        edit_client = QLineEdit(str(client or ""))
        edit_numero = QLineEdit(str(numero_client or ""))
        edit_total = QDoubleSpinBox()
        edit_total.setRange(0, 999999999999)
        edit_total.setDecimals(2)
        edit_total.setSuffix(" FC")
        edit_total.setValue(float(total or 0))

        edit_paye = QDoubleSpinBox()
        edit_paye.setRange(0, 999999999999)
        edit_paye.setDecimals(2)
        edit_paye.setSuffix(" FC")
        edit_paye.setValue(float(paye or 0))

        edit_echeance = QDateEdit()
        edit_echeance.setCalendarPopup(True)
        edit_echeance.setDisplayFormat("dd/MM/yyyy")

        try:
            edit_echeance.setDate(
                QDate.fromString(str(echeance), "dd/MM/yyyy")
            )
            if not edit_echeance.date().isValid():
                edit_echeance.setDate(QDate.currentDate())
        except Exception:
            edit_echeance.setDate(QDate.currentDate())

        form_mod.addWidget(QLabel("CLIENT"), 0, 0)
        form_mod.addWidget(edit_client, 0, 1)
        form_mod.addWidget(QLabel("N° CLIENT"), 1, 0)
        form_mod.addWidget(edit_numero, 1, 1)
        form_mod.addWidget(QLabel("MONTANT TOTAL"), 2, 0)
        form_mod.addWidget(edit_total, 2, 1)
        form_mod.addWidget(QLabel("TOTAL PAYÉ"), 3, 0)
        form_mod.addWidget(edit_paye, 3, 1)
        form_mod.addWidget(QLabel("ÉCHÉANCE"), 4, 0)
        form_mod.addWidget(edit_echeance, 4, 1)

        layout.addLayout(form_mod)

        avertissement = QLabel(
            "⚠️ La modification du montant payé est une correction administrative. "
            "Elle ne supprime pas l'historique des paiements déjà enregistré."
        )
        avertissement.setWordWrap(True)
        avertissement.setStyleSheet(
            "background:#FFF7ED;border:1px solid #FED7AA;"
            "border-radius:8px;padding:9px;color:#9A3412;"
        )
        layout.addWidget(avertissement)

        actions = QHBoxLayout()
        enregistrer = QPushButton("✓ ENREGISTRER LES MODIFICATIONS")
        annuler = QPushButton("ANNULER")
        actions.addWidget(enregistrer)
        actions.addWidget(annuler)
        layout.addLayout(actions)

        def appliquer_modification():
            nouveau_client = edit_client.text().strip()
            nouveau_numero = edit_numero.text().strip()
            nouveau_total = float(edit_total.value() or 0)
            nouveau_paye = float(edit_paye.value() or 0)
            nouvelle_echeance = edit_echeance.date().toString("dd/MM/yyyy")

            if not nouveau_client:
                QMessageBox.warning(
                    dlg, "MODIFICATION", "Le nom du client est obligatoire."
                )
                return

            if nouveau_total <= 0:
                QMessageBox.warning(
                    dlg, "MODIFICATION",
                    "Le montant total doit être supérieur à zéro."
                )
                return

            if nouveau_paye < 0 or nouveau_paye > nouveau_total:
                QMessageBox.warning(
                    dlg, "MODIFICATION",
                    "Le montant payé doit être compris entre 0 et le montant total."
                )
                return

            nouveau_solde = nouveau_total - nouveau_paye
            nouveau_statut = etat_credit(
                nouvelle_echeance, nouveau_solde
            )

            confirmation = QMessageBox.question(
                dlg,
                "CONFIRMER LA MODIFICATION",
                "Voulez-vous enregistrer les corrections apportées à ce crédit ?",
                QMessageBox.StandardButton.Yes |
                QMessageBox.StandardButton.No
            )
            if confirmation != QMessageBox.StandardButton.Yes:
                return

            dt = maintenant()
            conn = connexion()
            try:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE credits
                    SET client=?,
                        numero_client=?,
                        echeance=?,
                        montant_total=?,
                        montant_paye=?,
                        solde=?,
                        statut=?
                    WHERE id=?
                """, (
                    nouveau_client,
                    nouveau_numero,
                    nouvelle_echeance,
                    nouveau_total,
                    nouveau_paye,
                    nouveau_solde,
                    nouveau_statut,
                    credit_id
                ))

                enregistrer_audit_conn(
                    conn,
                    "MODIFICATION CRÉDIT",
                    reference,
                    f"Correction du crédit client {nouveau_client}",
                    nouveau_total
                )

                conn.execute("""
                    INSERT INTO journal
                    (date, heure, operation, reference, description, montant)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    dt.strftime("%d/%m/%Y"),
                    dt.strftime("%H:%M:%S"),
                    "MODIFICATION CRÉDIT",
                    reference,
                    "Correction du crédit client",
                    nouveau_total
                ))

                conn.commit()

            except Exception as exc:
                conn.rollback()
                conn.close()
                QMessageBox.critical(
                    dlg,
                    "MODIFICATION",
                    "Impossible de modifier le crédit :\n\n" + str(exc)
                )
                return

            conn.close()
            dlg.accept()

            QMessageBox.information(
                fenetre,
                "CRÉDIT MODIFIÉ",
                f"Le crédit {reference} a été corrigé avec succès."
            )
            charger_credits()

        enregistrer.clicked.connect(appliquer_modification)
        annuler.clicked.connect(dlg.reject)
        dlg.exec()

    def enregistrer_remboursement():
        credit = obtenir_credit_selectionne()
        if credit is None:
            return

        (
            credit_id, reference, client, numero_client,
            date_credit, echeance, total, paye, solde, statut
        ) = credit

        solde = float(solde or 0)

        if solde <= 0:
            QMessageBox.information(
                fenetre,
                "CRÉDIT",
                "Ce crédit est déjà entièrement payé."
            )
            return

        montant, ok = QInputDialog.getDouble(
            fenetre,
            "REMBOURSEMENT",
            f"Client : {client}\n"
            f"N° client : {numero_client or '—'}\n"
            f"Solde actuel : {formater_nombre(solde)} FC\n\n"
            f"Montant versé (FC) :",
            min(1000, solde),
            0,
            solde,
            2
        )
        if not ok or montant <= 0:
            return

        modes = [
            "ESPÈCES", "M-PESA", "AIRTEL MONEY",
            "ORANGE MONEY", "VIREMENT", "AUTRE"
        ]
        mode, ok = QInputDialog.getItem(
            fenetre,
            "MODE DE PAIEMENT",
            "Mode de paiement :",
            modes,
            0,
            False
        )
        if not ok:
            return

        observation, ok = QInputDialog.getText(
            fenetre,
            "REMBOURSEMENT",
            "Observation (facultatif) :"
        )
        if not ok:
            return

        dt = maintenant()
        nouveau_paye = float(paye or 0) + montant
        nouveau_solde = max(
            0,
            float(total or 0) - nouveau_paye
        )
        nouveau_statut = etat_credit(
            echeance, nouveau_solde
        )

        conn = connexion()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO credit_paiements
                (credit_id, date, heure, montant, mode_paiement, observation)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                credit_id,
                dt.strftime("%d/%m/%Y"),
                dt.strftime("%H:%M:%S"),
                montant,
                mode,
                observation
            ))

            cur.execute("""
                UPDATE credits
                SET montant_paye=?, solde=?, statut=?
                WHERE id=?
            """, (
                nouveau_paye,
                nouveau_solde,
                nouveau_statut,
                credit_id
            ))

            enregistrer_audit_conn(
                conn,
                "REMBOURSEMENT CRÉDIT",
                reference,
                f"Remboursement {mode} pour {client}",
                montant
            )

            conn.execute("""
                INSERT INTO journal
                (date, heure, operation, reference, description, montant)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                dt.strftime("%d/%m/%Y"),
                dt.strftime("%H:%M:%S"),
                "REMBOURSEMENT CRÉDIT",
                reference,
                f"Remboursement {mode} - {client}",
                montant
            ))

            conn.commit()

        except Exception as exc:
            conn.rollback()
            conn.close()
            QMessageBox.critical(
                fenetre,
                "REMBOURSEMENT",
                "Impossible d'enregistrer le paiement :\n\n" + str(exc)
            )
            return

        conn.close()

        QMessageBox.information(
            fenetre,
            "REMBOURSEMENT ENREGISTRÉ",
            f"Paiement enregistré.\n\n"
            f"Référence : {reference}\n"
            f"Montant : {formater_nombre(montant)} FC\n"
            f"Nouveau solde : {formater_nombre(nouveau_solde)} FC\n"
            f"État : {nouveau_statut}"
        )

        charger_credits()

    def historique_paiements():
        credit = obtenir_credit_selectionne()
        if credit is None:
            return

        credit_id, reference, client = (
            credit[0], credit[1], credit[2]
        )

        dlg = QDialog(fenetre)
        dlg.setWindowTitle(f"HISTORIQUE — {reference}")
        dlg.resize(850, 500)

        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(
            f"CLIENT : {client}    |    RÉFÉRENCE : {reference}"
        ))

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "ID", "DATE", "HEURE", "MONTANT", "MODE", "OBSERVATION"
        ])
        appliquer_tableau_standard(table)
        layout.addWidget(table)

        conn = connexion()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, date, heure, montant, mode_paiement, observation
            FROM credit_paiements
            WHERE credit_id=?
            ORDER BY id DESC
        """, (credit_id,))
        lignes = cur.fetchall()
        conn.close()

        table.setRowCount(len(lignes))

        for row, ligne in enumerate(lignes):
            ajouter_ligne_tableau(table, row, [
                ligne[0],
                ligne[1],
                ligne[2],
                formater_nombre(ligne[3]) + " FC",
                ligne[4],
                ligne[5] or ""
            ])

        fermer = QPushButton("FERMER")
        fermer.clicked.connect(dlg.accept)
        layout.addWidget(fermer)
        dlg.exec()

    def pdf_credit_selectionne():
        credit = obtenir_credit_selectionne()
        if credit is None:
            return
        credit_pdf(int(credit[0]))

    bouton_creer.clicked.connect(creer_credit)
    bouton_actualiser.clicked.connect(charger_credits)
    bouton_modifier.clicked.connect(modifier_credit)
    bouton_paiement.clicked.connect(enregistrer_remboursement)
    bouton_details.clicked.connect(historique_paiements)
    bouton_pdf.clicked.connect(pdf_credit_selectionne)

    recherche.returnPressed.connect(charger_credits)
    recherche.textChanged.connect(lambda: charger_credits())

    charger_credits()


# ============================================================
# FINANCE
# ============================================================

def afficher_finance():
    if not demander_mot_de_passe():
        return

    nettoyer_zone()
    contenu.addWidget(creer_titre("FINANCE", 30))

    dt = datetime.now()
    debut_mois = dt.replace(day=1).strftime("%Y-%m-%d")
    fin_jour = dt.strftime("%Y-%m-%d")

    benefice_total = benefice_global()
    benefice_mois = benefice_periode(debut_mois, fin_jour)
    benefice_jour = benefice_periode(fin_jour, fin_jour)
    produit, benefice_produit = produit_plus_rentable()
    marge = marge_moyenne()
    pa = valeur_stock_pa()
    pv = valeur_stock_pv()
    taux = obtenir_taux()

    historique = QTableWidget()
    historique.setColumnCount(3)
    historique.setHorizontalHeaderLabels([
        "DATE", "BÉNÉFICE (FC)", "BÉNÉFICE ($)"
    ])
    appliquer_tableau_standard(historique)

    conn = connexion()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            v.date,
            COALESCE(SUM(
                (vd.prix_fc - vd.prix_achat_fc) * vd.quantite
            ), 0)
        FROM vente_details vd
        JOIN ventes v ON v.id = vd.vente_id
        GROUP BY v.date
        ORDER BY
            substr(v.date, 7, 4),
            substr(v.date, 4, 2),
            substr(v.date, 1, 2)
    """)
    lignes = cur.fetchall()
    conn.close()

    historique.setRowCount(len(lignes))
    for row, ligne in enumerate(lignes):
        benef = float(ligne[1] or 0)
        usd = benef / taux if taux > 0 else 0
        ajouter_ligne_tableau(
            historique,
            row,
            [ligne[0], formater_nombre(benef) + " FC", f"{usd:.2f} $"]
        )

    grille = QGridLayout()
    rubriques = [
        ("BÉNÉFICE GLOBAL", formater_nombre(benefice_total) + " FC"),
        ("BÉNÉFICE DU MOIS", formater_nombre(benefice_mois) + " FC"),
        ("BÉNÉFICE DU JOUR", formater_nombre(benefice_jour) + " FC"),
        ("PRODUIT LE PLUS RENTABLE", str(produit)),
        ("MARGE MOYENNE", f"{marge:.2f} %"),
        ("BÉNÉFICE PRODUIT LE PLUS RENTABLE", formater_nombre(benefice_produit) + " FC"),
        ("VALEUR DU STOCK PA", formater_nombre(pa) + " FC"),
        ("VALEUR DU STOCK PA", f"{pa / taux:.2f} $" if taux > 0 else "0.00 $"),
        ("VALEUR DU STOCK PV", formater_nombre(pv) + " FC"),
        ("VALEUR DU STOCK PV", f"{pv / taux:.2f} $" if taux > 0 else "0.00 $"),
    ]

    icones_finance = ["💼", "📅", "☀️", "⭐", "📐", "🏆", "🧾", "💵", "🏷️", "💲"]
    for i, (nom, valeur) in enumerate(rubriques):
        grille.addWidget(
            creer_carte_dashboard(f"{icones_finance[i]}  {nom}", valeur, i),
            i // 3, i % 3
        )

    contenu.addLayout(grille)
    contenu.addWidget(QLabel("HISTORIQUE DES BÉNÉFICES"))
    contenu.addWidget(historique)
    contenu.addStretch()


# ============================================================
# PARAMÈTRES
# ============================================================

def afficher_parametres():
    nettoyer_zone()
    contenu.addWidget(creer_titre("PARAMÈTRES", 30))

    intro = QLabel(
        "Centre de configuration de l'application : devise, taux de change "
        "et règles de référence."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet(
        "color:#526173; font-size:14px; padding:0 4px 12px 4px;"
    )
    contenu.addWidget(intro)

    taux_actuel = obtenir_taux()

    # ------------------------------------------------------------
    # Carte principale du taux
    # ------------------------------------------------------------
    carte_taux = QFrame()
    carte_taux.setObjectName("carteTauxParametres")
    carte_taux.setStyleSheet("""
        QFrame#carteTauxParametres {
            background:#FFFFFF;
            border:1px solid #D7E0EA;
            border-left:5px solid #2878A8;
            border-radius:12px;
        }
    """)
    layout_taux = QHBoxLayout(carte_taux)
    layout_taux.setContentsMargins(20,16,20,16)
    layout_taux.setSpacing(18)

    bloc_info = QVBoxLayout()
    bloc_info.setSpacing(4)

    titre_taux = QLabel("TAUX DE CHANGE ACTUEL")
    titre_taux.setStyleSheet(
        "color:#60758A;font-size:11px;font-weight:800;border:none;"
    )
    bloc_info.addWidget(titre_taux)

    label_taux = QLabel(f"1 $ = {formater_nombre(taux_actuel)} FC")
    label_taux.setStyleSheet(
        "color:#2878A8;font-size:27px;font-weight:850;border:none;"
    )
    bloc_info.addWidget(label_taux)

    sous_taux = QLabel("Ce taux est utilisé pour les conversions USD ↔ FC.")
    sous_taux.setStyleSheet("color:#74869A;font-size:12px;border:none;")
    bloc_info.addWidget(sous_taux)
    layout_taux.addLayout(bloc_info, 1)

    bouton_taux = QPushButton("✎  MODIFIER LE TAUX")
    bouton_taux.setMinimumSize(190, 46)
    bouton_taux.setCursor(Qt.CursorShape.PointingHandCursor)
    bouton_taux.setToolTip("Afficher le clavier numérique du taux de change.")
    bouton_taux.setStyleSheet("""
        QPushButton {
            background:#2878A8;
            color:#FFFFFF;
            border:1px solid #21688F;
            border-radius:9px;
            padding:10px 18px;
            font-size:12px;
            font-weight:800;
        }
        QPushButton:hover { background:#328CBF; border-color:#2878A8; }
        QPushButton:pressed { background:#1F6387; }
    """)
    layout_taux.addWidget(bouton_taux, 0, Qt.AlignmentFlag.AlignVCenter)

    badge = QLabel("RÉFÉRENCE MONÉTAIRE")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet("""
        background:#EAF3F8;
        color:#2878A8;
        border:1px solid #C6DCE8;
        border-radius:16px;
        padding:8px 12px;
        font-size:11px;
        font-weight:800;
    """)
    layout_taux.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
    contenu.addWidget(carte_taux)

    # ------------------------------------------------------------
    # Éditeur du taux : clavier numérique VISIBLE directement
    # dans la page. Aucun QInputDialog ne dépend du clic.
    # ------------------------------------------------------------
    editeur_taux = QFrame()
    editeur_taux.setObjectName("editeurTaux")
    editeur_taux.setStyleSheet("""
        QFrame#editeurTaux {
            background:#FFFFFF;
            border:1px solid #D7E0EA;
            border-radius:12px;
        }
    """)
    editeur_layout = QHBoxLayout(editeur_taux)
    editeur_layout.setContentsMargins(18,14,18,14)
    editeur_layout.setSpacing(20)

    bloc_saisie = QVBoxLayout()
    bloc_saisie.setSpacing(8)

    titre_saisie = QLabel("MODIFICATION DU TAUX")
    titre_saisie.setStyleSheet(
        "color:#526173;font-size:12px;font-weight:800;border:none;"
    )
    bloc_saisie.addWidget(titre_saisie)

    champ_taux = QLineEdit()
    champ_taux.setObjectName("champTauxVisible")
    champ_taux.setAlignment(Qt.AlignmentFlag.AlignCenter)
    champ_taux.setMinimumHeight(52)
    champ_taux.setText(
        str(int(taux_actuel)) if float(taux_actuel).is_integer()
        else str(taux_actuel)
    )
    champ_taux.selectAll()
    champ_taux.setInputMethodHints(Qt.InputMethodHint.ImhFormattedNumbersOnly)
    champ_taux.setStyleSheet("""
        QLineEdit#champTauxVisible {
            background:#F8FBFD;
            color:#2878A8;
            border:2px solid #8DB7D2;
            border-radius:10px;
            font-size:24px;
            font-weight:800;
            padding:6px;
        }
        QLineEdit#champTauxVisible:focus { border:2px solid #2878A8; }
    """)
    bloc_saisie.addWidget(champ_taux)

    aide = QLabel("1 $ = combien de FC ?")
    aide.setAlignment(Qt.AlignmentFlag.AlignCenter)
    aide.setStyleSheet("color:#74869A;font-size:12px;font-weight:700;border:none;")
    bloc_saisie.addWidget(aide)

    editeur_layout.addLayout(bloc_saisie, 1)

    pave = QGridLayout()
    pave.setSpacing(6)

    def touche_numerique(texte_touche, ligne, colonne, largeur=1):
        touche = QPushButton(texte_touche)
        touche.setMinimumSize(58, 44)
        touche.setCursor(Qt.CursorShape.PointingHandCursor)
        touche.setStyleSheet("""
            QPushButton {
                background:#F5F8FB;
                color:#415A70;
                border:1px solid #D4DEE8;
                border-radius:8px;
                font-size:16px;
                font-weight:800;
                padding:5px;
            }
            QPushButton:hover { background:#EAF3F8; border-color:#8DB7D2; }
            QPushButton:pressed { background:#DCEBF4; }
        """)
        if texte_touche.isdigit():
            touche.clicked.connect(
                lambda _, c=texte_touche: champ_taux.insert(c)
            )
        elif texte_touche == ",":
            def ajouter_decimal():
                if "." not in champ_taux.text():
                    champ_taux.insert(".")
            touche.clicked.connect(ajouter_decimal)
        elif texte_touche == "⌫":
            touche.clicked.connect(champ_taux.backspace)
        elif texte_touche == "EFFACER":
            touche.clicked.connect(champ_taux.clear)
        pave.addWidget(touche, ligne, colonne, 1, largeur)
        return touche

    touche_numerique("7", 0, 0)
    touche_numerique("8", 0, 1)
    touche_numerique("9", 0, 2)
    touche_numerique("4", 1, 0)
    touche_numerique("5", 1, 1)
    touche_numerique("6", 1, 2)
    touche_numerique("1", 2, 0)
    touche_numerique("2", 2, 1)
    touche_numerique("3", 2, 2)
    touche_numerique("0", 3, 0)
    touche_numerique(",", 3, 1)
    touche_numerique("⌫", 3, 2)
    touche_numerique("EFFACER", 4, 0, 3)

    editeur_layout.addLayout(pave)

    actions_taux = QVBoxLayout()
    actions_taux.setSpacing(8)

    bouton_enregistrer_taux = QPushButton("✓  ENREGISTRER LE TAUX")
    bouton_enregistrer_taux.setMinimumSize(190, 46)
    bouton_enregistrer_taux.setCursor(Qt.CursorShape.PointingHandCursor)
    bouton_enregistrer_taux.setStyleSheet("""
        QPushButton {
            background:#2878A8;
            color:#FFFFFF;
            border:1px solid #21688F;
            border-radius:9px;
            padding:10px 16px;
            font-size:12px;
            font-weight:800;
        }
        QPushButton:hover { background:#328CBF; }
        QPushButton:pressed { background:#1F6387; }
    """)
    actions_taux.addWidget(bouton_enregistrer_taux)

    bouton_annuler_taux = QPushButton("ANNULER")
    bouton_annuler_taux.setMinimumSize(190, 40)
    bouton_annuler_taux.setCursor(Qt.CursorShape.PointingHandCursor)
    actions_taux.addWidget(bouton_annuler_taux)
    actions_taux.addStretch()
    editeur_layout.addLayout(actions_taux)

    contenu.addWidget(editeur_taux)

    def enregistrer_taux_visible():
        try:
            valeur = convertir_nombre(champ_taux.text())
        except Exception:
            QMessageBox.warning(
                fenetre,
                "Taux invalide",
                "Veuillez entrer un nombre valide."
            )
            champ_taux.setFocus()
            return

        if valeur <= 0:
            QMessageBox.warning(
                fenetre,
                "Taux invalide",
                "Le taux doit être supérieur à zéro."
            )
            champ_taux.setFocus()
            return

        enregistrer_taux(valeur)
        label_taux.setText(f"1 $ = {formater_nombre(valeur)} FC")

        try:
            enregistrer_journal(
                "MODIFICATION TAUX",
                "",
                f"Taux de change modifié : 1 USD = {formater_nombre(valeur)} FC",
                valeur
            )
        except Exception:
            pass

        QMessageBox.information(
            fenetre,
            "Taux enregistré",
            "Le taux de change a été enregistré avec succès.\n\n"
            f"1 $ = {formater_nombre(valeur)} FC"
        )

    def restaurer_taux_visible():
        actuel = obtenir_taux()
        champ_taux.setText(
            str(int(actuel)) if float(actuel).is_integer() else str(actuel)
        )
        champ_taux.selectAll()
        champ_taux.setFocus()

    bouton_enregistrer_taux.clicked.connect(enregistrer_taux_visible)
    bouton_annuler_taux.clicked.connect(restaurer_taux_visible)

    # Le bouton bleu existant sert maintenant à amener immédiatement
    # le curseur sur l'éditeur visible, sans ouvrir de boîte de dialogue.
    bouton_taux.clicked.connect(lambda: (
        champ_taux.setFocus(), champ_taux.selectAll()
    ))

    # Références de fonctionnement : conservées intactes.
    section = QGroupBox("CONFIGURATION MONÉTAIRE")
    section_layout = QVBoxLayout(section)
    section_layout.setSpacing(10)

    information = QLabel(
        "Le prix en FC reste la référence.\n"
        "Le prix en dollars ($) est calculé automatiquement à partir du taux enregistré.\n"
        "Toute modification du taux est enregistrée dans la traçabilité."
    )
    information.setWordWrap(True)
    information.setStyleSheet(
        "background:#F5F8FB;color:#526173;border:1px solid #E1E7EE;"
        "border-radius:8px;padding:12px;font-size:13px;"
    )
    section_layout.addWidget(information)
    contenu.addWidget(section)

    ref = QGroupBox("RÉFÉRENCES DE L'APPLICATION")
    ref_layout = QGridLayout(ref)
    refs = [
        ("Devise principale", "FC — Franc congolais"),
        ("Conversion", "1 USD = taux enregistré"),
        ("État stock", "Rupture / Faible / OK"),
        ("Stock faible", "Moins de 10 unités"),
    ]
    for i, (nom, valeur) in enumerate(refs):
        n = QLabel(nom)
        n.setStyleSheet("color:#526173;font-weight:700;padding:5px;")
        v = QLabel(valeur)
        v.setStyleSheet("color:#415A70;font-weight:600;padding:5px;")
        ref_layout.addWidget(n, i, 0)
        ref_layout.addWidget(v, i, 1)
    contenu.addWidget(ref)
    contenu.addStretch()

def afficher_a_propos():
    dlg = QDialog(fenetre)
    dlg.setWindowTitle("À propos — Billy-eLBERT STOCK")
    dlg.resize(760, 620)
    layout = QVBoxLayout(dlg)
    titre = QLabel("BILLY-eLBERT STOCK")
    titre.setStyleSheet("font-size:24px;font-weight:800;color:#176B78;padding:8px")
    layout.addWidget(titre)
    texte = QLabel("""
    <h2>Concepteur : MSc Ir. Billy KOKOSAL</h2>
    <p><b>Ingénieur civil des mines de formation</b>, issu de la Faculté Polytechnique, avec une expérience professionnelle orientée vers les opérations minières, la topographie de chantier et le suivi technique des travaux souterrains (underground).</p>
    <p>Son parcours associe la compréhension du terrain, la rigueur des mesures topographiques, le suivi des activités d'exploitation et l'analyse des données techniques. Cette approche pratique est mise au service de solutions numériques destinées à améliorer l'organisation, la traçabilité et la prise de décision.</p>
    <p><b>Billy-eLBERT STOCK</b> est une application de gestion conçue pour centraliser les produits, les stocks, les achats/réquisitions, les ventes, les indicateurs et l'historique des opérations dans une interface structurée.</p>
    <p style='color:#0F766E'><b>Conception et développement : eLBERT-SOFTWARE</b></p>
    <p style='color:#64748B'>Application développée avec Python, PySide6 et SQLite.</p>
    """)
    texte.setWordWrap(True)
    texte.setTextFormat(Qt.TextFormat.RichText)
    texte.setStyleSheet("font-size:14px;padding:12px;line-height:1.4")
    texte.setText(texte.text() + "<h3 style='color:#0F766E'>Parcours universitaire</h3><p>Ressortissant de l'Université nationale du Zaïre, actuellement <b>UNIVERSITÉ DE LUBUMBASHI</b>.</p><h3 style='color:#0F766E'>Coordonnées professionnelles</h3><p><b>Téléphone :</b> +243 813 946 260<br/><b>Téléphone :</b> +243 842 335 359</p><p>Pour les échanges professionnels, merci de préciser l'objet de votre demande et le service concerné.</p>")
    layout.addWidget(texte)
    fermer = QPushButton("Fermer")
    fermer.clicked.connect(dlg.accept)
    layout.addWidget(fermer)
    dlg.exec()


# ============================================================
# MODE DÉVELOPPEUR — OUTILS DE MISE À JOUR
# ============================================================

def _trouver_source_developpeur():
    """Retourne le fichier source externe à modifier/tester."""
    candidats = []

    # Une fois créée, la copie externe devient la source de travail officielle.
    # Cela évite de modifier directement le fichier utilisé pour construire l'EXE.
    candidats.append(DEV_SOURCE_FILE)

    # Lors de la toute première ouverture, on part du main.py actuellement exécuté.
    if not getattr(sys, "frozen", False):
        try:
            candidats.append(Path(__file__).resolve())
        except Exception:
            pass

    # Emplacements de secours pratiques sur le PC de développement.
    candidats.extend([
        DOSSIER / "Source" / "main.py",
        Path.cwd() / "main.py",
        Path.home() / "Desktop" / "Stock" / "main.py",
        Path.home() / "OneDrive" / "Desktop" / "Stock" / "main.py",
    ])

    vus = set()
    for candidat in candidats:
        try:
            candidat = candidat.resolve()
        except Exception:
            continue
        if str(candidat).lower() in vus:
            continue
        vus.add(str(candidat).lower())
        if candidat.exists() and candidat.is_file():
            return candidat

    return None


def _python_developpeur():
    """Trouve Python pour lancer une version source modifiée."""
    if not getattr(sys, "frozen", False):
        exe = Path(sys.executable)
        if exe.exists():
            return [str(exe)]

    python_exe = shutil.which("python") or shutil.which("python.exe")
    if python_exe:
        return [python_exe]

    py_launcher = shutil.which("py") or shutil.which("py.exe")
    if py_launcher:
        return [py_launcher, "-3"]

    return None


def _ouvrir_fichier_avec_editeur(fichier):
    """Ouvre le code avec VS Code si disponible, sinon avec l'éditeur Windows."""
    fichier = Path(fichier).resolve()

    candidats_vscode = [
        shutil.which("code"),
        shutil.which("code.cmd"),
        os.environ.get("LOCALAPPDATA", "") + r"\Programs\Microsoft VS Code\Code.exe",
        os.environ.get("ProgramFiles", "") + r"\Microsoft VS Code\Code.exe",
        os.environ.get("ProgramFiles(x86)", "") + r"\Microsoft VS Code\Code.exe",
    ]

    for candidat in candidats_vscode:
        if candidat and Path(candidat).exists():
            try:
                subprocess.Popen([str(candidat), str(fichier)], cwd=str(fichier.parent))
                return True
            except Exception:
                pass

    try:
        os.startfile(str(fichier))
        return True
    except Exception:
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(fichier)))
            return True
        except Exception:
            return False


def _ouvrir_dossier(fichier_ou_dossier):
    """Ouvre un dossier dans l'Explorateur Windows."""
    chemin = Path(fichier_ou_dossier).resolve()
    if chemin.is_file():
        chemin = chemin.parent
    try:
        os.startfile(str(chemin))
        return True
    except Exception:
        try:
            return QDesktopServices.openUrl(QUrl.fromLocalFile(str(chemin)))
        except Exception:
            return False


def _initialiser_source_developpeur():
    """Prépare la copie externe de travail si elle n'existe pas encore."""
    if DEV_SOURCE_FILE.exists():
        return DEV_SOURCE_FILE

    if getattr(sys, "frozen", False):
        return _trouver_source_developpeur()

    try:
        source_actuelle = Path(__file__).resolve()
        if source_actuelle.exists() and source_actuelle.suffix.lower() == ".py":
            shutil.copy2(source_actuelle, DEV_SOURCE_FILE)
            # Le logo est également copié pour que le test externe dispose
            # des mêmes ressources que l'application principale.
            source_ressources = source_actuelle.parent / "Ressources"
            destination_ressources = DEV_SOURCE_DIR / "Ressources"
            if source_ressources.exists():
                shutil.copytree(source_ressources, destination_ressources, dirs_exist_ok=True)
            return DEV_SOURCE_FILE
    except Exception as exc:
        QMessageBox.warning(
            fenetre,
            "Mode développeur",
            f"Impossible de préparer le code source externe :\n{exc}"
        )

    return _trouver_source_developpeur()


def sauvegarder_code_source():
    """Crée une copie horodatée du code source actuel."""
    source = _initialiser_source_developpeur()
    if not source or not source.exists():
        QMessageBox.warning(
            fenetre,
            "Code source introuvable",
            "Aucun main.py externe n'a été trouvé.\n\n"
            f"Placez le fichier source dans :\n{DEV_SOURCE_FILE}"
        )
        return

    try:
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = DEV_BACKUPS_DIR / f"main_backup_{horodatage}.py"
        shutil.copy2(source, destination)
        QMessageBox.information(
            fenetre,
            "Code sauvegardé",
            "Le code source a été sauvegardé avec succès.\n\n"
            f"Copie :\n{destination}"
        )
    except Exception as exc:
        QMessageBox.critical(
            fenetre,
            "Erreur de sauvegarde",
            f"Impossible de sauvegarder le code :\n{exc}"
        )


def creer_nouvelle_version_code():
    """Crée un instantané versionné du main.py actuel."""
    source = _initialiser_source_developpeur()
    if not source or not source.exists():
        QMessageBox.warning(
            fenetre,
            "Code source introuvable",
            "Impossible de créer une version : main.py est introuvable."
        )
        return

    version, ok = QInputDialog.getText(
        fenetre,
        "Créer une nouvelle version",
        "Nom de la version (ex. v1.0.1) :",
        text="v" + datetime.now().strftime("%Y.%m.%d")
    )
    if not ok:
        return

    version = version.strip() or ("v" + datetime.now().strftime("%Y.%m.%d"))
    version = "".join(c for c in version if c.isalnum() or c in "._-")
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = DEV_VERSIONS_DIR / f"main_{version}_{horodatage}.py"

    try:
        shutil.copy2(source, destination)
        QMessageBox.information(
            fenetre,
            "Nouvelle version",
            "Nouvelle version créée avec succès.\n\n"
            f"{destination}"
        )
    except Exception as exc:
        QMessageBox.critical(
            fenetre,
            "Erreur de version",
            f"Impossible de créer la version :\n{exc}"
        )


def restaurer_derniere_version_code():
    """Restaure la dernière version enregistrée dans le dossier Versions."""
    source = _initialiser_source_developpeur()
    if not source:
        QMessageBox.warning(
            fenetre,
            "Code source introuvable",
            "Impossible de restaurer une version : main.py est introuvable."
        )
        return

    versions = sorted(
        DEV_VERSIONS_DIR.glob("main_*.py"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if not versions:
        QMessageBox.information(
            fenetre,
            "Aucune version",
            "Aucune version enregistrée n'est disponible dans :\n"
            f"{DEV_VERSIONS_DIR}"
        )
        return

    derniere = versions[0]
    confirmation = QMessageBox.question(
        fenetre,
        "Restaurer la dernière version",
        "Voulez-vous remplacer le code actuel par :\n\n"
        f"{derniere.name}\n\n"
        "Une copie de sécurité du code actuel sera créée avant la restauration.",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if confirmation != QMessageBox.StandardButton.Yes:
        return

    try:
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(source, DEV_BACKUPS_DIR / f"avant_restauration_{horodatage}.py")
        shutil.copy2(derniere, source)
        QMessageBox.information(
            fenetre,
            "Restauration terminée",
            "La dernière version a été restaurée.\n\n"
            "Utilisez « Recharger l'application » pour charger le nouveau code."
        )
    except Exception as exc:
        QMessageBox.critical(
            fenetre,
            "Erreur de restauration",
            f"Impossible de restaurer la version :\n{exc}"
        )


def tester_version_modifiee():
    """Lance le main.py externe dans un nouveau processus Python."""
    source = _initialiser_source_developpeur()
    if not source or not source.exists():
        QMessageBox.warning(
            fenetre,
            "Test impossible",
            "Le main.py à tester est introuvable.\n\n"
            f"Emplacement attendu :\n{DEV_SOURCE_FILE}"
        )
        return

    python_cmd = _python_developpeur()
    if not python_cmd:
        QMessageBox.critical(
            fenetre,
            "Python introuvable",
            "Python n'a pas été trouvé sur cet ordinateur.\n\n"
            "Installez Python ou ajoutez python.exe au PATH pour tester "
            "la version modifiée."
        )
        return

    try:
        subprocess.Popen(
            python_cmd + [str(source)],
            cwd=str(source.parent)
        )
        QMessageBox.information(
            fenetre,
            "Test lancé",
            "La version modifiée vient d'être lancée dans une nouvelle fenêtre.\n\n"
            f"Source testée :\n{source}"
        )
    except Exception as exc:
        QMessageBox.critical(
            fenetre,
            "Erreur de test",
            f"Impossible de lancer la version modifiée :\n{exc}"
        )


def recharger_application():
    """Redémarre l'application et charge le code source externe s'il existe."""
    confirmation = QMessageBox.question(
        fenetre,
        "Recharger l'application",
        "L'application va être redémarrée pour charger les modifications.\n\n"
        "Voulez-vous continuer ?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    if confirmation != QMessageBox.StandardButton.Yes:
        return

    try:
        source = _trouver_source_developpeur()
        python_cmd = _python_developpeur()

        # En mode développeur, on recharge la copie externe modifiable.
        if source and source.exists() and python_cmd:
            subprocess.Popen(
                python_cmd + [str(source)],
                cwd=str(source.parent)
            )
        elif getattr(sys, "frozen", False):
            # Secours : si Python n'est pas disponible, on relance l'EXE.
            subprocess.Popen([sys.executable], cwd=str(Path(sys.executable).parent))
        else:
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve())],
                cwd=str(Path(__file__).resolve().parent)
            )

        QTimer.singleShot(250, app.quit)
    except Exception as exc:
        QMessageBox.critical(
            fenetre,
            "Erreur de rechargement",
            f"Impossible de redémarrer l'application :\n{exc}"
        )


def ouvrir_code_source():
    """Ouvre le fichier source externe dans l'éditeur."""
    source = _initialiser_source_developpeur()
    if not source:
        QMessageBox.warning(
            fenetre,
            "Code source introuvable",
            "Aucun main.py n'a été trouvé.\n\n"
            f"Placez votre source dans :\n{DEV_SOURCE_FILE}"
        )
        return

    if not _ouvrir_fichier_avec_editeur(source):
        QMessageBox.warning(
            fenetre,
            "Ouverture impossible",
            f"Impossible d'ouvrir :\n{source}"
        )


def afficher_mode_developpeur():
    """Ouvre le mode développeur uniquement après authentification."""
    if ANDROID:
        QMessageBox.information(
            fenetre,
            "Mode développeur",
            "Le mode développeur de la version Windows est désactivé sur Android."
        )
        return

    # Sécurité : le mode développeur n'est jamais ouvert automatiquement.
    mot_de_passe, ok = QInputDialog.getText(
        fenetre,
        "ACCÈS DÉVELOPPEUR",
        "Mot de passe développeur :",
        QLineEdit.EchoMode.Password
    )
    if not ok or mot_de_passe != "0813946260":
        if ok:
            QMessageBox.warning(
                fenetre,
                "ACCÈS REFUSÉ",
                "Mot de passe développeur incorrect."
            )
        return

    source = _initialiser_source_developpeur()

    dlg = QDialog(fenetre)
    dlg.setWindowTitle("🛠 MODE DÉVELOPPEUR")
    dlg.resize(620, 560)

    layout = QVBoxLayout(dlg)
    layout.setSpacing(10)

    titre = QLabel("🛠 MODE DÉVELOPPEUR")
    titre.setStyleSheet(
        "font-size:24px;font-weight:800;color:#0F766E;padding:8px 4px;"
    )
    layout.addWidget(titre)

    info = QLabel(
        "Zone cachée réservée à la maintenance du logiciel.\n"
        "Les modifications du code peuvent être testées sans reconstruire l'EXE."
    )
    info.setWordWrap(True)
    info.setStyleSheet("padding:4px;color:#334155;font-size:13px;")
    layout.addWidget(info)

    chemin = QLabel(
        f"SOURCE : {source if source else DEV_SOURCE_FILE}\n"
        f"VERSIONS : {DEV_VERSIONS_DIR}\n"
        f"SAUVEGARDES : {DEV_BACKUPS_DIR}"
    )
    chemin.setWordWrap(True)
    chemin.setStyleSheet(
        "background:#F8FAFC;border:1px solid #E2E8F0;"
        "border-radius:8px;padding:10px;color:#475569;"
    )
    layout.addWidget(chemin)

    boutons = [
        ("📂 Ouvrir le code source", ouvrir_code_source),
        ("✏️ Modifier le code", ouvrir_code_source),
        ("▶️ Tester la version modifiée", tester_version_modifiee),
        ("🔄 Recharger l'application", recharger_application),
        ("💾 Sauvegarder le code", sauvegarder_code_source),
        ("📦 Créer une nouvelle version", creer_nouvelle_version_code),
        ("↩️ Restaurer la dernière version", restaurer_derniere_version_code),
    ]

    for texte_bouton, fonction in boutons:
        bouton = QPushButton(texte_bouton)
        bouton.setMinimumHeight(42)
        bouton.setStyleSheet(
            "QPushButton{background:#FFFFFF;border:1px solid #CBD5E1;"
            "border-radius:8px;padding:8px 14px;text-align:left;"
            "font-weight:700;}"
            "QPushButton:hover{background:#EFF6FF;border-color:#93C5FD;}"
            "QPushButton:pressed{background:#DBEAFE;}"
        )
        bouton.clicked.connect(fonction)
        layout.addWidget(bouton)

    note = QLabel(
        "⚠️ Après une modification, utilisez « Tester la version modifiée ».\n"
        "L'EXE installé ne change pas tant qu'une nouvelle reconstruction n'est pas faite."
    )
    note.setWordWrap(True)
    note.setStyleSheet(
        "background:#FFF7ED;border:1px solid #FED7AA;"
        "border-radius:8px;padding:10px;color:#9A3412;"
    )
    layout.addWidget(note)

    fermer = QPushButton("Fermer")
    fermer.clicked.connect(dlg.accept)
    layout.addWidget(fermer)

    dlg.exec()


# Raccourci caché : Ctrl + Shift + Alt + B.
action_mode_developpeur = QAction("Mode développeur", fenetre)
action_mode_developpeur.setShortcut(QKeySequence("Ctrl+Shift+Alt+B"))
action_mode_developpeur.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
action_mode_developpeur.triggered.connect(afficher_mode_developpeur)
fenetre.addAction(action_mode_developpeur)


# ============================================================
# CONNEXIONS DES MENUS
# ============================================================

bouton_tableau.clicked.connect(afficher_accueil)
bouton_produits.clicked.connect(afficher_produits)
bouton_stock.clicked.connect(afficher_stock)
bouton_achats.clicked.connect(afficher_achats)
bouton_ventes.clicked.connect(afficher_ventes)
bouton_statistiques.clicked.connect(afficher_statistiques)
bouton_finance.clicked.connect(afficher_finance)
bouton_credits.clicked.connect(afficher_credits)
bouton_journal_audit.clicked.connect(afficher_historique_audit)
bouton_parametres.clicked.connect(afficher_parametres)

def enregistrer_rapide_sans_mot_de_passe():
    """Enregistrement rapide : SQLite valide les écritures; cette action force commit et crée une archive."""
    try:
        conn = connexion()
        conn.commit()
        conn.close()
        if BASE.exists():
            ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
            horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(BASE, ARCHIVES_DIR / f"sauvegarde_rapide_{horodatage}.db")
        QMessageBox.information(fenetre, "Enregistrement", "Les données ont été enregistrées et une copie de sécurité a été créée.")
    except Exception as exc:
        QMessageBox.critical(fenetre, "Erreur d'enregistrement", f"Impossible de créer la sauvegarde :\n{exc}")


# Raccourci de sauvegarde rapide, comme dans Word/Excel (Ctrl+S).
action_sauvegarder_rapide = QAction("Enregistrer", fenetre)
action_sauvegarder_rapide.setShortcut(QKeySequence.StandardKey.Save)
action_sauvegarder_rapide.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
action_sauvegarder_rapide.triggered.connect(enregistrer_rapide_sans_mot_de_passe)
fenetre.addAction(action_sauvegarder_rapide)




# ============================================================
# ASSEMBLAGE
# ============================================================

# Barre d'actions rapide : accès à l'enregistrement sans bouton dans le menu latéral.
barre_rapide = QHBoxLayout()
barre_rapide.addStretch()
bouton_enregistrer_rapide = QPushButton("💾 Enregistrer  (Ctrl+S)")
bouton_enregistrer_rapide.setToolTip("Enregistrer maintenant et créer une copie de sécurité — sans mot de passe")
bouton_enregistrer_rapide.clicked.connect(enregistrer_rapide_sans_mot_de_passe)
bouton_enregistrer_rapide.setStyleSheet("background:#0F766E;color:white;font-weight:bold;padding:8px 14px;border-radius:6px")
# Ajout au-dessus de la zone centrale si celle-ci possède déjà un layout.
if contenu_widget.layout() is not None:
    contenu_widget.layout().insertLayout(0, barre_rapide)
    barre_rapide.addWidget(bouton_enregistrer_rapide)
else:
    barre_rapide.addWidget(bouton_enregistrer_rapide)
    principal.addLayout(barre_rapide)

# ============================================================
# CONTENEURS DÉFILANTS — PROTECTION CONTRE LE ZOOM / PETITS ÉCRANS
# ============================================================
# Le redimensionnement ou le zoom Windows ne supprime aucune donnée :
# le contenu devient simplement défilable lorsqu'il ne tient plus à l'écran.
menu_scroll = QScrollArea()
menu_scroll.setWidgetResizable(True)
menu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
menu_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
menu_scroll.setFrameShape(QFrame.Shape.NoFrame)
menu_scroll.setFixedWidth(262)
menu_scroll.setWidget(menu_widget)

contenu_scroll = QScrollArea()
contenu_scroll.setWidgetResizable(True)
contenu_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
contenu_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
contenu_scroll.setFrameShape(QFrame.Shape.NoFrame)
contenu_scroll.setWidget(contenu_widget)

principal.addWidget(menu_scroll)
principal.addWidget(contenu_scroll, 1)


# ============================================================
# DÉMARRAGE
# ============================================================

def sauvegarde_fermeture():
    if MODE_FINAL and BASE.exists():
        try:
            ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
            horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(BASE, ARCHIVES_DIR / f"fermeture_{horodatage}.db")
        except Exception:
            pass


app.aboutToQuit.connect(sauvegarde_fermeture)

# Actualise périodiquement le compteur visible sans modifier les autres éléments.
timer_compteur_licence = QTimer()
timer_compteur_licence.setInterval(60 * 1000)
timer_compteur_licence.timeout.connect(mettre_a_jour_compteur_licence)
timer_compteur_licence.start()

afficher_accueil()
mettre_a_jour_compteur_licence()

fenetre.show()

# La fenêtre s'affiche d'abord avec les boutons désactivés.
# Ensuite seulement, la boîte d'activation apparaît.
QTimer.singleShot(250, verifier_licence_apres_ouverture)

sys.exit(app.exec())
