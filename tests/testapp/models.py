from django.db import models

from deidentify.mixins import ConfidentialFields, ConfidentialTable
from deidentify.sql import jsonb_set_keys, seq_digits, seq_email, seq_text
from deidentify.util import create_incrementing_faker


class Secret(ConfidentialTable, models.Model):
    """A model whose table should be emptied entirely."""


class MappedRow(ConfidentialFields, models.Model):
    """Exercises all three field-mapping value forms."""

    faked = models.CharField(max_length=50, blank=True)
    code = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)
    account_number = models.CharField(max_length=50, blank=True)

    _anonymizer_field_map = {
        "faked": lambda f: f.first_name,  # 1-arg callable
        "code": lambda f, previous: lambda: f"anon-{previous}",  # 2-arg callable
        "country": "REDACTED",  # plain string literal
        "account_number": create_incrementing_faker(20000, "A{:05d}"),
    }


class BaseWithSecret(ConfidentialFields, models.Model):
    """Abstract base declaring its own redacted field."""

    name = models.CharField(max_length=50, blank=True)
    _anonymizer_field_map = {"name": lambda f: f.sentence}

    class Meta:
        abstract = True


class ChildWithOwnSecret(BaseWithSecret):
    """A subclass with its own map: the inherited redaction on `name` must
    survive alongside the subclass's own `note` redaction (MRO merge)."""

    note = models.CharField(max_length=50, blank=True)
    _anonymizer_field_map = {"note": lambda f: f.sentence}


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
        "note": lambda f: f.sentence,
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
