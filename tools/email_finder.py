#!/usr/bin/env python3
"""
Email Finder — Genere et verifie les emails professionnels
a partir d'un fichier Excel de contacts.

Usage:
    python email_finder.py contacts.xlsx [output.csv]

Colonnes attendues dans l'Excel (insensible a la casse) :
    - nom (ou last_name, family_name)
    - prenom (ou first_name, given_name)
    - societe (ou company, entreprise, organisation)
    - site_web (ou website, url) — optionnel
    - linkedin (ou linkedin_url, profil_linkedin) — optionnel (pour info, pas scrape)

Dependances :
    pip install openpyxl dnspython
"""

import csv
import re
import smtplib
import socket
import sys
import time
import unicodedata
from pathlib import Path
from typing import NamedTuple

import dns.resolver
import openpyxl

# ============================================================================
# Configuration
# ============================================================================

# Patterns d'email a generer ({p} = initiale prenom, {prenom}/{nom} = complet)
EMAIL_PATTERNS = [
    "{prenom}.{nom}",
    "{p}.{nom}",
    "{p}{nom}",
    "{prenom}",
    "{nom}.{prenom}",
    "{nom}",
    "{prenom}{nom}",
    "{nom}{p}",
]

# Extensions de domaine a tester si pas de site web
DOMAIN_EXTENSIONS = [".fr", ".com", ".io", ".eu", ".net", ".co"]

# Timeout SMTP en secondes
SMTP_TIMEOUT = 10

# Delai entre chaque verification SMTP (anti-rate-limit)
SMTP_DELAY = 1.5

# Nombre max de tentatives SMTP par domaine avant abandon
MAX_SMTP_FAILURES_PER_DOMAIN = 3

# Mapping des noms de colonnes reconnus
COLUMN_ALIASES = {
    "nom": ["nom", "last_name", "family_name", "name", "last name"],
    "prenom": ["prenom", "prénom", "first_name", "given_name", "first name"],
    "societe": ["societe", "société", "company", "entreprise", "organisation", "organization"],
    "site_web": ["site_web", "site web", "website", "url", "site", "web"],
    "linkedin": ["linkedin", "linkedin_url", "profil_linkedin", "profil linkedin", "linkedin url"],
}


# ============================================================================
# Types
# ============================================================================


class Contact(NamedTuple):
    nom: str
    prenom: str
    societe: str
    site_web: str
    linkedin: str


class EmailResult(NamedTuple):
    prenom: str
    nom: str
    societe: str
    domaine: str
    email: str
    pattern: str
    mx_valide: bool
    smtp_statut: str  # "valide", "invalide", "inconnu", "catch_all", "erreur"
    linkedin: str


# ============================================================================
# Normalisation des noms
# ============================================================================


def normalize_name(name: str) -> str:
    """Normalise un nom : supprime accents, minuscules, gere tirets/espaces."""
    if not name:
        return ""
    # Supprimer accents
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ASCII", "ignore").decode("ASCII")
    # Minuscules, supprimer espaces/tirets, garder que alphanum
    ascii_name = ascii_name.lower().strip()
    # Gerer les noms composes : "Jean-Pierre" → "jeanpierre" ou "jean-pierre"
    # On garde sans tiret pour les patterns email
    ascii_name = re.sub(r"[^a-z]", "", ascii_name)
    return ascii_name


def extract_domain_from_url(url: str) -> str:
    """Extrait le domaine d'une URL."""
    if not url:
        return ""
    url = url.strip().lower()
    # Supprimer protocole
    url = re.sub(r"^https?://", "", url)
    # Supprimer www.
    url = re.sub(r"^www\.", "", url)
    # Supprimer path
    domain = url.split("/")[0]
    # Supprimer port
    domain = domain.split(":")[0]
    return domain


def normalize_company_for_domain(company: str) -> str:
    """Transforme un nom de societe en candidat de domaine."""
    if not company:
        return ""
    name = company.lower().strip()
    # Supprimer formes juridiques courantes
    legal_forms = [
        r"\bsas\b", r"\bsa\b", r"\bsarl\b", r"\bsarl\b", r"\beurl\b",
        r"\bsci\b", r"\bgmbh\b", r"\bltd\b", r"\binc\b", r"\bllc\b",
        r"\bgroup\b", r"\bgroupe\b",
    ]
    for form in legal_forms:
        name = re.sub(form, "", name)
    # Supprimer accents
    nfkd = unicodedata.normalize("NFKD", name)
    name = nfkd.encode("ASCII", "ignore").decode("ASCII")
    # Garder que alphanum et tirets
    name = re.sub(r"[^a-z0-9-]", "", name)
    # Supprimer tirets multiples et en debut/fin
    name = re.sub(r"-+", "-", name).strip("-")
    return name


# ============================================================================
# DNS / MX
# ============================================================================

# Cache des lookups MX
_mx_cache: dict[str, list[str]] = {}
# Domaines bloques (trop d'echecs SMTP)
_blocked_domains: dict[str, int] = {}


def get_mx_servers(domain: str) -> list[str]:
    """Recupere les serveurs MX d'un domaine, tries par priorite."""
    if domain in _mx_cache:
        return _mx_cache[domain]

    try:
        answers = dns.resolver.resolve(domain, "MX")
        mx_list = sorted(answers, key=lambda r: r.preference)
        servers = [str(r.exchange).rstrip(".") for r in mx_list]
        _mx_cache[domain] = servers
        return servers
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.resolver.Timeout, Exception):
        _mx_cache[domain] = []
        return []


def domain_has_mx(domain: str) -> bool:
    """Verifie si un domaine a des enregistrements MX."""
    return len(get_mx_servers(domain)) > 0


# ============================================================================
# Verification SMTP
# ============================================================================


def verify_email_smtp(email: str, mx_servers: list[str]) -> str:
    """
    Verifie une adresse email via SMTP RCPT TO.

    Retourne :
    - "valide" : le serveur accepte l'adresse (250)
    - "invalide" : le serveur rejette (550, 553, etc.)
    - "catch_all" : le serveur accepte tout (detecte)
    - "inconnu" : impossible de determiner (greylisting, timeout, etc.)
    - "erreur" : erreur de connexion
    """
    domain = email.split("@")[1]

    # Verifier si le domaine est bloque
    if _blocked_domains.get(domain, 0) >= MAX_SMTP_FAILURES_PER_DOMAIN:
        return "inconnu"

    for mx_server in mx_servers[:2]:  # Tester max 2 MX
        try:
            with smtplib.SMTP(mx_server, 25, timeout=SMTP_TIMEOUT) as smtp:
                smtp.ehlo("mail.fast-growth.fr")
                smtp.mail("verify@fast-growth.fr")
                code, _ = smtp.rcpt(email)
                if code == 250:
                    return "valide"
                if code in (550, 551, 552, 553, 554):
                    return "invalide"
                # 450, 451, 452 = temporaire (greylisting)
                return "inconnu"
        except smtplib.SMTPServerDisconnected:
            _blocked_domains[domain] = _blocked_domains.get(domain, 0) + 1
            return "inconnu"
        except (smtplib.SMTPConnectError, smtplib.SMTPResponseException,
                socket.timeout, socket.error, OSError):
            _blocked_domains[domain] = _blocked_domains.get(domain, 0) + 1
            continue

    return "erreur"


def detect_catch_all(domain: str, mx_servers: list[str]) -> bool:
    """Detecte si un domaine est catch-all en testant une adresse fictive."""
    fake_email = f"xz9q7w3k_test_invalid_12345@{domain}"
    result = verify_email_smtp(fake_email, mx_servers)
    return result == "valide"


# Cache catch-all
_catch_all_cache: dict[str, bool] = {}


# ============================================================================
# Generation d'emails
# ============================================================================


def generate_emails(prenom: str, nom: str, domain: str) -> list[tuple[str, str]]:
    """Genere toutes les variantes d'email pour un contact. Retourne [(email, pattern)]."""
    p_norm = normalize_name(prenom)
    n_norm = normalize_name(nom)

    if not p_norm or not n_norm or not domain:
        return []

    initial = p_norm[0]
    results = []
    seen = set()

    for pattern in EMAIL_PATTERNS:
        local = pattern.format(prenom=p_norm, nom=n_norm, p=initial)
        email = f"{local}@{domain}"
        if email not in seen:
            seen.add(email)
            results.append((email, pattern))

    return results


# ============================================================================
# Resolution de domaine depuis nom de societe
# ============================================================================


def guess_domain(company: str) -> str:
    """Essaie de deviner le domaine d'une societe en testant les MX."""
    base = normalize_company_for_domain(company)
    if not base:
        return ""

    for ext in DOMAIN_EXTENSIONS:
        candidate = base + ext
        if domain_has_mx(candidate):
            return candidate

    return ""


# ============================================================================
# Lecture Excel
# ============================================================================


def detect_columns(headers: list[str]) -> dict[str, int]:
    """Detecte les colonnes par leurs noms (insensible a la casse)."""
    mapping = {}
    headers_lower = [h.lower().strip() if h else "" for h in headers]

    for field, aliases in COLUMN_ALIASES.items():
        for i, header in enumerate(headers_lower):
            if header in aliases:
                mapping[field] = i
                break

    return mapping


def read_excel(filepath: str) -> list[Contact]:
    """Lit le fichier Excel et retourne une liste de contacts."""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        print("[ERREUR] Aucune feuille active dans le fichier Excel.")
        sys.exit(1)

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        print("[ERREUR] Fichier vide ou sans donnees.")
        sys.exit(1)

    headers = [str(h) if h else "" for h in rows[0]]
    col_map = detect_columns(headers)

    # Verifier colonnes obligatoires
    missing = []
    for field in ["nom", "prenom", "societe"]:
        if field not in col_map:
            missing.append(field)
    if missing:
        print(f"[ERREUR] Colonnes manquantes : {', '.join(missing)}")
        print(f"         Colonnes trouvees : {headers}")
        print(f"         Noms acceptes : {COLUMN_ALIASES}")
        sys.exit(1)

    contacts = []
    for row in rows[1:]:
        nom = str(row[col_map["nom"]] or "").strip()
        prenom = str(row[col_map["prenom"]] or "").strip()
        societe = str(row[col_map["societe"]] or "").strip()
        site_web = str(row[col_map.get("site_web", -1)] or "").strip() if "site_web" in col_map else ""
        linkedin = str(row[col_map.get("linkedin", -1)] or "").strip() if "linkedin" in col_map else ""

        if nom and prenom and societe:
            contacts.append(Contact(
                nom=nom, prenom=prenom, societe=societe,
                site_web=site_web, linkedin=linkedin,
            ))

    wb.close()
    return contacts


# ============================================================================
# Pipeline principal
# ============================================================================


def process_contacts(contacts: list[Contact]) -> list[EmailResult]:
    """Traite tous les contacts : generation + verification."""
    results: list[EmailResult] = []
    total = len(contacts)
    # Grouper par societe pour optimiser les lookups domaine
    domain_cache: dict[str, str] = {}

    for i, contact in enumerate(contacts, 1):
        company_key = contact.societe.lower().strip()
        progress = f"[{i}/{total}]"

        # Resoudre le domaine
        if company_key in domain_cache:
            domain = domain_cache[company_key]
        elif contact.site_web:
            domain = extract_domain_from_url(contact.site_web)
            if domain and not domain_has_mx(domain):
                print(f"  {progress} {contact.prenom} {contact.nom} — domaine {domain} sans MX, tentative auto...")
                domain = guess_domain(contact.societe)
            domain_cache[company_key] = domain
        else:
            domain = guess_domain(contact.societe)
            domain_cache[company_key] = domain

        if not domain:
            print(f"  {progress} {contact.prenom} {contact.nom} @ {contact.societe} — domaine introuvable")
            results.append(EmailResult(
                prenom=contact.prenom, nom=contact.nom, societe=contact.societe,
                domaine="", email="", pattern="", mx_valide=False,
                smtp_statut="domaine_introuvable", linkedin=contact.linkedin,
            ))
            continue

        mx_servers = get_mx_servers(domain)
        if not mx_servers:
            print(f"  {progress} {contact.prenom} {contact.nom} @ {domain} — pas de MX")
            results.append(EmailResult(
                prenom=contact.prenom, nom=contact.nom, societe=contact.societe,
                domaine=domain, email="", pattern="", mx_valide=False,
                smtp_statut="pas_de_mx", linkedin=contact.linkedin,
            ))
            continue

        # Detecter catch-all (une fois par domaine)
        if domain not in _catch_all_cache:
            _catch_all_cache[domain] = detect_catch_all(domain, mx_servers)
            if _catch_all_cache[domain]:
                print(f"  {progress} {domain} — catch-all detecte (verification limitee)")
            time.sleep(SMTP_DELAY)

        is_catch_all = _catch_all_cache[domain]

        # Generer les variantes
        emails = generate_emails(contact.prenom, contact.nom, domain)
        print(f"  {progress} {contact.prenom} {contact.nom} @ {domain} — {len(emails)} variantes")

        for email, pattern in emails:
            if is_catch_all:
                smtp_status = "catch_all"
            else:
                smtp_status = verify_email_smtp(email, mx_servers)
                time.sleep(SMTP_DELAY)

            results.append(EmailResult(
                prenom=contact.prenom, nom=contact.nom, societe=contact.societe,
                domaine=domain, email=email, pattern=pattern,
                mx_valide=True, smtp_statut=smtp_status, linkedin=contact.linkedin,
            ))

            # Si on trouve un email valide, on continue quand meme (tous les patterns demandes)

    return results


# ============================================================================
# Export CSV
# ============================================================================


CSV_HEADERS = [
    "prenom", "nom", "societe", "domaine", "email", "pattern",
    "mx_valide", "smtp_statut", "linkedin",
]


def write_csv(results: list[EmailResult], output_path: str) -> None:
    """Ecrit les resultats dans un fichier CSV."""
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(CSV_HEADERS)
        for r in results:
            writer.writerow([
                r.prenom, r.nom, r.societe, r.domaine, r.email, r.pattern,
                "oui" if r.mx_valide else "non", r.smtp_statut, r.linkedin,
            ])


def print_summary(results: list[EmailResult]) -> None:
    """Affiche un resume des resultats."""
    total_contacts = len(set((r.prenom, r.nom, r.societe) for r in results))
    total_emails = len([r for r in results if r.email])
    valides = len([r for r in results if r.smtp_statut == "valide"])
    invalides = len([r for r in results if r.smtp_statut == "invalide"])
    catch_all = len([r for r in results if r.smtp_statut == "catch_all"])
    inconnus = len([r for r in results if r.smtp_statut == "inconnu"])
    sans_domaine = len([r for r in results if not r.domaine])

    print("\n" + "=" * 50)
    print("RESUME")
    print("=" * 50)
    print(f"  Contacts traites   : {total_contacts}")
    print(f"  Emails generes     : {total_emails}")
    print(f"  Valides (SMTP 250) : {valides}")
    print(f"  Invalides          : {invalides}")
    print(f"  Catch-all          : {catch_all}")
    print(f"  Inconnus           : {inconnus}")
    print(f"  Sans domaine       : {sans_domaine}")
    print("=" * 50)


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python email_finder.py contacts.xlsx [output.csv]")
        print("\nColonnes attendues : nom, prenom, societe, site_web (optionnel), linkedin (optionnel)")
        sys.exit(1)

    input_file = sys.argv[1]
    if not Path(input_file).exists():
        print(f"[ERREUR] Fichier introuvable : {input_file}")
        sys.exit(1)

    output_file = sys.argv[2] if len(sys.argv) > 2 else Path(input_file).stem + "_emails.csv"

    print(f"\n{'=' * 50}")
    print(f"EMAIL FINDER — Fast Growth Advisor")
    print(f"{'=' * 50}")
    print(f"  Input  : {input_file}")
    print(f"  Output : {output_file}")
    print()

    # Lire les contacts
    print("[1/3] Lecture du fichier Excel...")
    contacts = read_excel(input_file)
    print(f"       {len(contacts)} contacts trouves\n")

    # Traiter
    print("[2/3] Generation et verification des emails...")
    results = process_contacts(contacts)

    # Exporter
    print(f"\n[3/3] Export CSV...")
    write_csv(results, output_file)
    print(f"       Ecrit dans {output_file}")

    # Resume
    print_summary(results)


if __name__ == "__main__":
    main()
