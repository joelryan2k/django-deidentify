import logging
from inspect import signature
from itertools import chain, islice

import faker
from django.conf import settings

from deidentify.mixins import FIELD_MAPPING, FIELD_MAPPING_VALUE
from deidentify.model_actions import NoAction, ObscureFields, TruncateTable
from deidentify.policy import build_policy
from deidentify.util import enumerate_models, enumerate_tables

logger = logging.getLogger(__name__)


def chunks(iterable, size):
    iterator = iter(iterable)
    for first in iterator:
        yield chain([first], islice(iterator, size - 1))


def count_parameters(p: FIELD_MAPPING_VALUE):
    if callable(p):
        sig = signature(p)

        return len(sig.parameters)

    return None


def anonymize_model(model_klass, fake: faker.Faker, mapping: FIELD_MAPPING):
    if not settings.DEBUG:
        raise Exception("Will not run unless DEBUG is True")

    logger.info("Anonymizing %s", model_klass)

    columns = mapping.keys()

    total = 0

    parameter_counts_by_column_mapping = {
        k: count_parameters(v) for k, v in mapping.items()
    }

    for chunk in chunks(model_klass.objects.all().only(*columns).iterator(), 20000):
        entities = list(chunk)
        for entity in entities:
            for column in columns:
                value = getattr(entity, column)
                if value:
                    fake_fn_or_literal = mapping[column]
                    if (
                        callable(fake_fn_or_literal)
                        and parameter_counts_by_column_mapping[column] == 2
                    ):
                        new_value = fake_fn_or_literal(fake, value)()  # type: ignore
                    elif callable(fake_fn_or_literal):
                        new_value = fake_fn_or_literal(fake)()  # type: ignore
                    else:
                        new_value = fake_fn_or_literal

                    setattr(entity, column, new_value)

        total += len(entities)
        model_klass.objects.bulk_update(entities, columns)
        logger.info("%s: %s", model_klass, total)


def truncate_model(model_klass):
    if not settings.DEBUG:
        raise Exception("Will not run unless DEBUG is True")

    logger.info("Truncating %s", model_klass)

    model_klass.objects.all().delete()


def anonymize():
    if not settings.DEBUG:
        raise Exception("Will not run unless DEBUG is True")

    policy = build_policy()
    fake = faker.Faker()
    all_tables = list(enumerate_tables())

    for app, model in enumerate_models():
        if model._meta.db_table in all_tables:
            all_tables.remove(model._meta.db_table)

        model_policy = policy.model_policies.get((app.name, model))

        if not model_policy:
            raise Exception(f"Missing policy for {app.name}:{model}")

        if isinstance(model_policy, NoAction):
            continue

        if isinstance(model_policy, TruncateTable):
            truncate_model(model)
            continue

        if isinstance(model_policy, ObscureFields):
            if len(model_policy.field_map):
                logger.info("Anonymizing table %s:%s", app, model)
                anonymize_model(model, fake, model_policy.field_map)

            if model_policy.post_action:
                logger.info("Running post action %s:%s", app, model)
                model_policy.post_action()

            continue

    if len(all_tables):
        logger.warning("Unhandled tables: %s", all_tables)
