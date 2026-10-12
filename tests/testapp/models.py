from datetime import date

from django.db import models

from deidentify.mixins import ConfidentialFields, ConfidentialTable
from deidentify.sql import fake_date, jsonb_set_keys, seq_digits, seq_email, seq_text


class Secret(ConfidentialTable, models.Model):
    """A model whose table should be emptied entirely."""


class BaseWithSecret(ConfidentialFields, models.Model):
    """Abstract base declaring its own redacted field."""

    name = models.CharField(max_length=50, blank=True)
    _anonymizer_field_map = {"name": seq_text("Name")}

    class Meta:
        abstract = True


class ChildWithOwnSecret(BaseWithSecret):
    """A subclass with its own map: the inherited redaction on `name` must
    survive alongside the subclass's own `note` redaction (MRO merge)."""

    note = models.CharField(max_length=50, blank=True)
    _anonymizer_field_map = {"note": seq_text("Note")}


class SqlRow(ConfidentialFields, models.Model):
    """Exercises the SQL-side value forms (literals and expressions)."""

    label = models.CharField(max_length=50, blank=True, null=True)
    email = models.CharField(max_length=50, blank=True)
    digits = models.CharField(max_length=9, blank=True)
    note = models.CharField(max_length=50, blank=True)

    _anonymizer_field_map = {
        "label": "REDACTED",
        "email": seq_email(),
        "digits": seq_digits(9),
        "note": seq_text("Note"),
    }


class JsonRow(ConfidentialFields, models.Model):
    """Postgres-only: jsonb_set_keys."""

    raw_data = models.TextField(blank=True)

    _anonymizer_field_map = {
        "raw_data": jsonb_set_keys(
            "raw_data", first_name="", illustration_name=seq_text("Illustration")
        ),
    }


class ConcreteParent(ConfidentialFields, models.Model):
    """Multi-table inheritance: the parent's field lives on a different table."""

    name = models.CharField(max_length=50, blank=True)
    _anonymizer_field_map = {"name": seq_text("Parent")}


class ConcreteChild(ConcreteParent):
    secret = models.CharField(max_length=50, blank=True)
    _anonymizer_field_map = {"secret": seq_text("Secret")}


class DateRow(ConfidentialFields, models.Model):
    """Postgres-only: fake_date."""

    born = models.DateField(null=True)
    _anonymizer_field_map = {"born": fake_date(date(1950, 1, 1), date(1999, 12, 31))}
