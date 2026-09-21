from django.conf import settings
from django.db.models import Model
from django.utils.module_loading import import_string

from deidentify.model_actions import (
    MODEL_ACTIONS,
    NoAction,
    ObscureFields,
    TruncateTable,
)

from .mixins import FIELD_MAPPING, AnonymizerModelPolicy
from .util import enumerate_models


class AnonymizerPolicy:
    def __init__(self):
        self.model_policies: dict[tuple[str, type[Model]], MODEL_ACTIONS] = {}


def merge_anonymizer_field_map(model: type) -> FIELD_MAPPING:
    """Merge ``_anonymizer_field_map`` across the model's MRO.

    A subclass that declares its own map extends (not replaces) the maps of its
    bases, so an inherited redaction can never be silently dropped by a subclass
    forgetting to re-list it. Walking the MRO base-first means a subclass can
    still override a specific field's strategy. Each class contributes only its
    *own* declared map (``__dict__``), so an inherited attribute is not counted
    twice.
    """
    merged: FIELD_MAPPING = {}
    for klass in reversed(model.__mro__):
        merged.update(klass.__dict__.get("_anonymizer_field_map", {}))
    return merged


def build_policy() -> AnonymizerPolicy:
    policy = AnonymizerPolicy()

    for app, model in enumerate_models():
        model_policy_value = getattr(model, "_anonymizer_policy", None)

        if not model_policy_value:
            continue

        if model_policy_value == AnonymizerModelPolicy.NO_ACTION:
            policy.model_policies[(app.name, model)] = NoAction()
        elif model_policy_value == AnonymizerModelPolicy.TRUNCATE_TABLE:
            policy.model_policies[(app.name, model)] = TruncateTable()
        elif model_policy_value == AnonymizerModelPolicy.OBSCURE_FIELDS:
            policy.model_policies[(app.name, model)] = ObscureFields(
                merge_anonymizer_field_map(model),
                None,
            )
        else:
            raise ValueError(f"Unknown policy {model_policy_value!r} on {model}")

    hook_path = getattr(settings, "DEIDENTIFY_POLICY_HOOK", None)
    if hook_path:
        import_string(hook_path)(policy)

    return policy
