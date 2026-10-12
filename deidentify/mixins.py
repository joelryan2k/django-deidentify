from enum import Enum

from django.db.models.expressions import Combinable


class AnonymizerModelPolicy(Enum):
    NO_ACTION = 1
    OBSCURE_FIELDS = 2
    TRUNCATE_TABLE = 3


class NotConfidential:
    _anonymizer_policy = AnonymizerModelPolicy.NO_ACTION


FIELD_MAPPING_VALUE = Combinable | str | int | float | None
FIELD_MAPPING = dict[str, FIELD_MAPPING_VALUE]


class ConfidentialFields:
    _anonymizer_policy = AnonymizerModelPolicy.OBSCURE_FIELDS
    _anonymizer_field_map: FIELD_MAPPING = {}


class ConfidentialTable:
    _anonymizer_policy = AnonymizerModelPolicy.TRUNCATE_TABLE
