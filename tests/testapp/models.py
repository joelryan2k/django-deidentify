from django.db import models

from deidentify.mixins import ConfidentialFields, ConfidentialTable
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
        "code": lambda f, previous: (lambda: f"anon-{previous}"),  # 2-arg callable
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
