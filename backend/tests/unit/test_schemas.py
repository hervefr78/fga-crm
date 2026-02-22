# =============================================================================
# FGA CRM - Tests unitaires des schemas Pydantic
# =============================================================================

import pytest
from pydantic import ValidationError

from app.schemas.activity import ACTIVITY_TYPES, ActivityCreate, ActivityUpdate
from app.schemas.company import CompanyCreate
from app.schemas.contact import ContactCreate
from app.schemas.deal import DealCreate
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
