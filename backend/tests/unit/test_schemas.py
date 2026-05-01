# =============================================================================
# FGA CRM - Tests unitaires des schemas Pydantic
# =============================================================================

import pytest
from pydantic import ValidationError

from app.schemas.activity import ACTIVITY_TYPES, ActivityCreate, ActivityUpdate
from app.schemas.company import CompanyCreate
from app.schemas.contact import ContactCreate
from app.schemas.deal import DealCreate, DealUpdate
from app.schemas.task import (
    TASK_PRIORITIES,
    TASK_TYPES,
    TaskCompletionToggle,
    TaskCreate,
    TaskUpdate,
)

# ---------------------------------------------------------------------------
# TaskCreate
# ---------------------------------------------------------------------------

class TestTaskCreate:
    """Tests de validation du schema TaskCreate."""

    def test_valid_minimal(self):
        task = TaskCreate(title="Appeler le client")
        assert task.title == "Appeler le client"
        assert task.type == "todo"
        assert task.priority == "medium"

    def test_valid_full(self):
        task = TaskCreate(
            title="Reunion",
            description="Preparer la demo",
            type="meeting",
            priority="high",
            due_date="2026-03-01T10:00:00",
            contact_id="12345678-1234-1234-1234-123456789012",
        )
        assert task.type == "meeting"
        assert task.priority == "high"

    def test_all_valid_types(self):
        for t in TASK_TYPES:
            task = TaskCreate(title="Test", type=t)
            assert task.type == t

    def test_all_valid_priorities(self):
        for p in TASK_PRIORITIES:
            task = TaskCreate(title="Test", priority=p)
            assert task.priority == p

    def test_invalid_type(self):
        with pytest.raises(ValidationError, match="Type invalide"):
            TaskCreate(title="Test", type="invalid_type")

    def test_invalid_priority(self):
        with pytest.raises(ValidationError, match="Priorite invalide"):
            TaskCreate(title="Test", priority="critical")

    def test_title_required(self):
        with pytest.raises(ValidationError):
            TaskCreate()

    def test_title_empty(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="")

    def test_title_max_length(self):
        # 500 caracteres = OK
        task = TaskCreate(title="A" * 500)
        assert len(task.title) == 500
        # 501 = KO
        with pytest.raises(ValidationError):
            TaskCreate(title="A" * 501)

    def test_description_max_length(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="Test", description="A" * 5001)


# ---------------------------------------------------------------------------
# TaskUpdate
# ---------------------------------------------------------------------------

class TestTaskUpdate:
    """Tests de validation du schema TaskUpdate."""

    def test_empty_update(self):
        update = TaskUpdate()
        assert update.title is None
        assert update.type is None

    def test_partial_update(self):
        update = TaskUpdate(title="Nouveau titre")
        assert update.title == "Nouveau titre"
        assert update.type is None

    def test_invalid_type_on_update(self):
        with pytest.raises(ValidationError, match="Type invalide"):
            TaskUpdate(type="nope")


# ---------------------------------------------------------------------------
# TaskCompletionToggle
# ---------------------------------------------------------------------------

class TestTaskCompletionToggle:
    def test_toggle_true(self):
        t = TaskCompletionToggle(is_completed=True)
        assert t.is_completed is True

    def test_toggle_false(self):
        t = TaskCompletionToggle(is_completed=False)
        assert t.is_completed is False

    def test_missing_field(self):
        with pytest.raises(ValidationError):
            TaskCompletionToggle()


# ---------------------------------------------------------------------------
# ActivityCreate
# ---------------------------------------------------------------------------

class TestActivityCreate:
    """Tests de validation du schema ActivityCreate."""

    def test_valid_minimal(self):
        a = ActivityCreate(type="call")
        assert a.type == "call"
        assert a.subject is None

    def test_valid_full(self):
        a = ActivityCreate(
            type="email",
            subject="Relance Q1",
            content="Contenu du mail...",
            contact_id="12345678-1234-1234-1234-123456789012",
        )
        assert a.type == "email"
        assert a.subject == "Relance Q1"

    def test_all_valid_types(self):
        for t in ACTIVITY_TYPES:
            a = ActivityCreate(type=t)
            assert a.type == t

    def test_invalid_type(self):
        with pytest.raises(ValidationError, match="Type invalide"):
            ActivityCreate(type="sms")

    def test_type_required(self):
        with pytest.raises(ValidationError):
            ActivityCreate()

    def test_subject_max_length(self):
        with pytest.raises(ValidationError):
            ActivityCreate(type="note", subject="A" * 501)

    def test_content_max_length(self):
        with pytest.raises(ValidationError):
            ActivityCreate(type="note", content="A" * 10001)


# ---------------------------------------------------------------------------
# ActivityUpdate
# ---------------------------------------------------------------------------

class TestActivityUpdate:
    def test_empty_update(self):
        u = ActivityUpdate()
        assert u.type is None

    def test_invalid_type(self):
        with pytest.raises(ValidationError, match="Type invalide"):
            ActivityUpdate(type="fax")


# ---------------------------------------------------------------------------
# CompanyCreate
# ---------------------------------------------------------------------------

class TestCompanyCreate:
    def test_valid_minimal(self):
        c = CompanyCreate(name="Acme Inc.")
        assert c.name == "Acme Inc."

    def test_name_required(self):
        with pytest.raises(ValidationError):
            CompanyCreate()


# ---------------------------------------------------------------------------
# ContactCreate
# ---------------------------------------------------------------------------

class TestContactCreate:
    def test_valid_minimal(self):
        c = ContactCreate(first_name="Jean", last_name="Dupont")
        assert c.first_name == "Jean"

    def test_first_name_required(self):
        with pytest.raises(ValidationError):
            ContactCreate(last_name="Dupont")


# ---------------------------------------------------------------------------
# DealCreate
# ---------------------------------------------------------------------------

class TestDealCreate:
    def test_valid_minimal(self):
        d = DealCreate(title="Deal Q1")
        assert d.title == "Deal Q1"

    def test_title_required(self):
        with pytest.raises(ValidationError):
            DealCreate()

    def test_deal_create_pricing_type_default(self):
        """Sans pricing_type explicite, le defaut doit etre 'one_shot'."""
        d = DealCreate(title="Deal sans pricing")
        assert d.pricing_type == "one_shot"

    def test_deal_create_pricing_type_valid_one_shot(self):
        d = DealCreate(title="Deal", pricing_type="one_shot")
        assert d.pricing_type == "one_shot"

    def test_deal_create_pricing_type_valid_monthly(self):
        # recurring_amount obligatoire pour un pricing recurrent (cross-field)
        d = DealCreate(title="Deal", pricing_type="monthly", recurring_amount=500)
        assert d.pricing_type == "monthly"

    def test_deal_create_pricing_type_valid_quarterly(self):
        d = DealCreate(title="Deal", pricing_type="quarterly", recurring_amount=1500)
        assert d.pricing_type == "quarterly"

    def test_deal_create_pricing_type_valid_biannual(self):
        d = DealCreate(title="Deal", pricing_type="biannual", recurring_amount=3000)
        assert d.pricing_type == "biannual"

    def test_deal_create_pricing_type_valid_annual(self):
        d = DealCreate(title="Deal", pricing_type="annual", recurring_amount=6000)
        assert d.pricing_type == "annual"

    def test_deal_create_pricing_type_invalid(self):
        """'weekly' n'est pas un pricing_type valide → ValidationError."""
        with pytest.raises(ValidationError, match="Pricing type invalide"):
            DealCreate(title="Deal", pricing_type="weekly")

    def test_deal_create_recurring_amount_negative(self):
        """recurring_amount negatif doit lever ValidationError (ge=0)."""
        with pytest.raises(ValidationError):
            DealCreate(title="Deal", recurring_amount=-100)

    def test_deal_create_recurring_amount_zero_is_valid(self):
        """recurring_amount=0 est la borne inferieure valide."""
        d = DealCreate(title="Deal", recurring_amount=0)
        assert d.recurring_amount == 0.0

    def test_deal_create_commitment_months_zero(self):
        """commitment_months=0 doit lever ValidationError (ge=1)."""
        with pytest.raises(ValidationError):
            DealCreate(title="Deal", commitment_months=0)

    def test_deal_create_commitment_months_too_high(self):
        """commitment_months=200 doit lever ValidationError (le=120)."""
        with pytest.raises(ValidationError):
            DealCreate(title="Deal", commitment_months=200)

    def test_deal_create_commitment_months_min_valid(self):
        """commitment_months=1 est la borne inferieure valide."""
        d = DealCreate(title="Deal", commitment_months=1)
        assert d.commitment_months == 1

    def test_deal_create_commitment_months_max_valid(self):
        """commitment_months=120 est la borne superieure valide."""
        d = DealCreate(title="Deal", commitment_months=120)
        assert d.commitment_months == 120

    def test_deal_create_recurring_fields_none_by_default(self):
        """Sans champs recurrents, recurring_amount et commitment_months sont None."""
        d = DealCreate(title="Deal")
        assert d.recurring_amount is None
        assert d.commitment_months is None


# ---------------------------------------------------------------------------
# DealUpdate — pricing_type validation
# ---------------------------------------------------------------------------

class TestDealUpdatePricingType:
    """Tests de validation des champs pricing du schema DealUpdate."""

    def test_deal_update_pricing_type_invalid(self):
        """pricing_type='weekly' sur un update → ValidationError."""
        with pytest.raises(ValidationError, match="Pricing type invalide"):
            DealUpdate(pricing_type="weekly")

    def test_deal_update_pricing_type_none_skipped(self):
        """pricing_type=None sur un update est autorise (champ optionnel)."""
        u = DealUpdate(pricing_type=None)
        assert u.pricing_type is None

    def test_deal_update_pricing_type_valid(self):
        """pricing_type valide sur update passe la validation."""
        u = DealUpdate(pricing_type="annual")
        assert u.pricing_type == "annual"

    def test_deal_update_recurring_amount_negative(self):
        """recurring_amount negatif sur update → ValidationError."""
        with pytest.raises(ValidationError):
            DealUpdate(recurring_amount=-1)

    def test_deal_update_commitment_months_zero(self):
        """commitment_months=0 sur update → ValidationError."""
        with pytest.raises(ValidationError):
            DealUpdate(commitment_months=0)

    def test_deal_update_commitment_months_exceeds_max(self):
        """commitment_months=121 sur update → ValidationError."""
        with pytest.raises(ValidationError):
            DealUpdate(commitment_months=121)
