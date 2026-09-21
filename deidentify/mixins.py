from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from faker import Faker


class AnonymizerModelPolicy(Enum):
    NO_ACTION = 1
    OBSCURE_FIELDS = 2
    TRUNCATE_TABLE = 3


class NotConfidential:
    _anonymizer_policy = AnonymizerModelPolicy.NO_ACTION


MAPPING_FUNCTION = Callable[["Faker"], Callable]
MAPPING_WITH_PREVIOUS_FUNCTION = Callable[["Faker", str], Callable]
FIELD_MAPPING_VALUE = MAPPING_WITH_PREVIOUS_FUNCTION | MAPPING_FUNCTION | str
FIELD_MAPPING = dict[str, FIELD_MAPPING_VALUE]


class ConfidentialFields:
    _anonymizer_policy = AnonymizerModelPolicy.OBSCURE_FIELDS
    _anonymizer_field_map: FIELD_MAPPING = {}


class ConfidentialTable:
    _anonymizer_policy = AnonymizerModelPolicy.TRUNCATE_TABLE
