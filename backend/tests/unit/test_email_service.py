# =============================================================================
# FGA CRM - Tests unitaires du service email
# =============================================================================

from types import SimpleNamespace

import pytest

from app.services.email import (
    _build_mime_message,
    build_variables_dict,
    extract_variables,
    substitute_variables,
)

# ---------- extract_variables ----------


class TestExtractVariables:
    def test_basic(self):
        result = extract_variables("Bonjour {{first_name}} {{last_name}}")
        assert result == ["first_name", "last_name"]

    def test_dedup_and_sort(self):
        result = extract_variables("{{b}} {{a}} {{b}} {{a}}")
        assert result == ["a", "b"]

    def test_empty_text(self):
        result = extract_variables("Pas de variables ici")
        assert result == []

    def test_nested_braces(self):
        result = extract_variables("{{{name}}}")
        assert result == ["name"]


# ---------- substitute_variables ----------


class TestSubstituteVariables:
    def test_basic_replacement(self):
        result = substitute_variables(
            "Bonjour {{first_name}} !",
            {"first_name": "Jean"},
        )
        assert result == "Bonjour Jean !"

    def test_unknown_variable_kept(self):
        result = substitute_variables(
            "Hello {{unknown_var}}",
            {"first_name": "Jean"},
        )
        assert result == "Hello {{unknown_var}}"

    def test_empty_dict(self):
        text = "{{first_name}} {{last_name}}"
        result = substitute_variables(text, {})
        assert result == text

    def test_multiple_replacements(self):
        result = substitute_variables(
            "{{first_name}} {{last_name}} ({{email}})",
            {"first_name": "Jean", "last_name": "Dupont", "email": "jean@co.com"},
        )
        assert result == "Jean Dupont (jean@co.com)"


# ---------- build_variables_dict ----------


class TestBuildVariablesDict:
    def _make_sender(self):
        return SimpleNamespace(full_name="Herve Martin")

    def _make_contact(self, company=None):
        return SimpleNamespace(
            first_name="Jean",
            last_name="Dupont",
            email="jean@exemple.com",
            title="CTO",
            company=company,
        )

    def _make_company(self):
        return SimpleNamespace(name="Acme Corp")

    @pytest.fixture(autouse=True)
    def patch_settings(self, monkeypatch):
        monkeypatch.setattr("app.services.email.settings.ovh_email_user", "crm@fga.fr")

    def test_with_contact_and_company(self):
        sender = self._make_sender()
        contact = self._make_contact()
        company = self._make_company()

        result = build_variables_dict(contact, company, sender)

        assert result["first_name"] == "Jean"
        assert result["last_name"] == "Dupont"
        assert result["full_name"] == "Jean Dupont"
        assert result["email"] == "jean@exemple.com"
        assert result["title"] == "CTO"
        assert result["company_name"] == "Acme Corp"
        assert result["sender_name"] == "Herve Martin"
        assert result["sender_email"] == "crm@fga.fr"

    def test_no_contact(self):
        sender = self._make_sender()
        result = build_variables_dict(None, None, sender)

        assert "first_name" not in result
        assert "last_name" not in result
        assert result["sender_name"] == "Herve Martin"
        assert result["sender_email"] == "crm@fga.fr"

    def test_contact_with_company_relation(self):
        """Company prise depuis la relation contact.company si pas de company separee."""
        company = self._make_company()
        contact = self._make_contact(company=company)
        sender = self._make_sender()

        result = build_variables_dict(contact, None, sender)
        assert result["company_name"] == "Acme Corp"


# ---------- _build_mime_message ----------


class TestBuildMimeMessage:
    def test_message_format(self):
        msg = _build_mime_message(
            to_email="dest@test.com",
            subject="Test Subject",
            body="Hello World",
            from_email="sender@test.com",
        )

        assert msg["Subject"] == "Test Subject"
        assert msg["To"] == "dest@test.com"
        assert msg["From"] == "sender@test.com"

        # Verifier les 2 parts (plain + html)
        parts = msg.get_payload()
        assert len(parts) == 2
        assert parts[0].get_content_type() == "text/plain"
        assert parts[1].get_content_type() == "text/html"

    def test_message_with_from_name(self):
        msg = _build_mime_message(
            to_email="dest@test.com",
            subject="Test",
            body="Body",
            from_email="herve@fga.fr",
            from_name="Herve Martin",
        )

        assert msg["From"] == "Herve Martin <herve@fga.fr>"
