import typing

from deidentify.mixins import FIELD_MAPPING


class ObscureFields:
    def __init__(self, field_map: FIELD_MAPPING, post_action: typing.Callable | None):
        self.field_map = field_map
        self.post_action = post_action


class TruncateTable:
    pass


class NoAction:
    pass


MODEL_ACTIONS = ObscureFields | TruncateTable | NoAction
