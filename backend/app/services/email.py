# =============================================================================
# FGA CRM - Service Email (envoi SMTP + substitution variables)
# =============================================================================

import html
import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.user import User

logger = logging.getLogger(__name__)

# Pattern pour extraire les variables {{nom}}
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class EmailSendError(Exception):
    """Erreur lors de l'envoi d'un email via SMTP."""


# ---------- Substitution de variables ----------


def extract_variables(text: str) -> list[str]:
    """Extraire les noms de variables depuis un texte contenant {{var}}.

    Retourne une liste triee et dedupliquee.
    """
    matches = VARIABLE_PATTERN.findall(text)
    return sorted(set(matches))


def substitute_variables(text: str, variables: dict[str, str]) -> str:
    """Remplacer {{var}} dans le texte par les valeurs du dictionnaire.

    Les variables inconnues sont laissees telles quelles (safe).
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return VARIABLE_PATTERN.sub(replacer, text)


def build_variables_dict(
    contact: Contact | None,
    company: Company | None,
    sender: User,
) -> dict[str, str]:
    """Construire le dictionnaire de substitution a partir des entites."""
    variables: dict[str, str] = {
        "sender_name": sender.full_name or "",
        "sender_email": settings.ovh_email_user or "",
    }

    if contact:
        variables["first_name"] = contact.first_name or ""
        variables["last_name"] = contact.last_name or ""
        variables["full_name"] = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
        variables["email"] = contact.email or ""
        variables["title"] = contact.title or ""

    if company:
        variables["company_name"] = company.name or ""
    elif contact and hasattr(contact, "company") and contact.company:
        variables["company_name"] = contact.company.name or ""

    return variables


# ---------- Envoi SMTP ----------


def _build_mime_message(
    to_email: str,
    subject: str,
    body: str,
    from_email: str,
    from_name: str | None = None,
) -> MIMEMultipart:
    """Construire un message MIME multipart/alternative (plain + HTML)."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["To"] = to_email

    if from_name:
        msg["From"] = f"{from_name} <{from_email}>"
    else:
        msg["From"] = from_email

    # Plain text
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # HTML basique : sauter les lignes + escaper le contenu
    html_body = html.escape(body).replace("\n", "<br>\n")
    html_content = (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'></head>"
        f"<body style='font-family: sans-serif; line-height: 1.6; color: #333;'>{html_body}</body>"
        "</html>"
    )
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    return msg


async def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str | None = None,
    from_name: str | None = None,
) -> str | None:
    """Envoyer un email via SMTP OVH (aiosmtplib).

    Retourne le message_id SMTP en cas de succes.
    Leve EmailSendError en cas d'echec (DC2 — jamais silencieux).
    """
    smtp_host = settings.ovh_smtp_host
    smtp_port = settings.ovh_smtp_port
    smtp_user = settings.ovh_email_user
    smtp_password = settings.ovh_email_password

    if not smtp_user or not smtp_password:
        raise EmailSendError("Configuration SMTP incomplete : email ou mot de passe manquant")

    sender = from_email or smtp_user
    msg = _build_mime_message(to_email, subject, body, sender, from_name)

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_password,
            use_tls=True,
            timeout=30,
        )

        # aiosmtplib.send retourne un tuple (dict, str)
        # Le message_id est dans l'en-tete du message
        message_id = msg.get("Message-ID")
        logger.info("[EmailService] Email envoye a %s (message_id=%s)", to_email, message_id)
        return message_id

    except aiosmtplib.SMTPException as e:
        logger.error("[EmailService] Echec envoi SMTP a %s : %s", to_email, str(e))
        raise EmailSendError(f"Erreur SMTP : {e}") from e
    except Exception as e:
        logger.error("[EmailService] Erreur inattendue envoi a %s : %s", to_email, str(e))
        raise EmailSendError(f"Erreur d'envoi : {e}") from e
