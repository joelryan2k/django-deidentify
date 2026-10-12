import logging
from collections import defaultdict

from django.conf import settings
from django.db import connection
from django.db.models import Case, CharField, F, Max, Min, Q, TextField, Value, When
from django.db.models.expressions import Combinable

from deidentify import util
from deidentify.mixins import FIELD_MAPPING
from deidentify.model_actions import NoAction, ObscureFields, TruncateTable
from deidentify.policy import build_policy
from deidentify.sql import ensure_functions
from deidentify.util import (
    enumerate_database_cache_tables,
    enumerate_models,
    enumerate_tables,
    enumerate_unmanaged_tables,
    truncate_table,
)

logger = logging.getLogger(__name__)


def is_sql_value(value) -> bool:
    return value is None or isinstance(value, (Combinable, str, int, float))


def validate_field_map(model_klass, mapping: FIELD_MAPPING):
    for column, value in mapping.items():
        if not is_sql_value(value):
            raise TypeError(
                f"{model_klass.__name__}.{column}: field-map values must be literals or Django "
                f"expressions (see deidentify.sql), got {value!r}"
            )


def guarded(field, value):
    expression = value if isinstance(value, Combinable) else Value(value)
    present = Q(**{f"{field.name}__isnull": False})
    if isinstance(field, (CharField, TextField)):
        present &= ~Q(**{field.name: ""})
    return Case(
        When(present, then=expression), default=F(field.name), output_field=field
    )


def anonymize_model(model_klass, mapping: FIELD_MAPPING):
    if not util.is_enabled():
        raise Exception(
            "Will not run unless DEBUG or DEIDENTIFY_ALLOW_WITHOUT_DEBUG is True"
        )

    validate_field_map(model_klass, mapping)
    logger.info("Anonymizing %s", model_klass)

    ensure_functions(connection)
    batch_size = getattr(settings, "DEIDENTIFY_UPDATE_BATCH_SIZE", None)

    updates_by_table_model = defaultdict(dict)
    for column, value in mapping.items():
        field = model_klass._meta.get_field(column)
        updates_by_table_model[field.model][column] = guarded(field, value)

    for table_model, updates in updates_by_table_model.items():
        queryset = table_model._base_manager.all()
        if table_model is not model_klass:
            queryset = queryset.filter(pk__in=model_klass._base_manager.values("pk"))
        table = table_model._meta.db_table

        if not batch_size:
            logger.info("%s (%s): %s", model_klass, table, queryset.update(**updates))
            continue

        bounds = queryset.aggregate(lo=Min("pk"), hi=Max("pk"))
        if bounds["lo"] is None:
            continue
        total = 0
        for lo in range(bounds["lo"], bounds["hi"] + 1, batch_size):
            total += queryset.filter(pk__gte=lo, pk__lt=lo + batch_size).update(
                **updates
            )
            logger.info("%s (%s): %s", model_klass, table, total)


def truncate_model(model_klass):
    if not util.is_enabled():
        raise Exception(
            "Will not run unless DEBUG or DEIDENTIFY_ALLOW_WITHOUT_DEBUG is True"
        )

    logger.info("Truncating %s", model_klass)

    model_klass.objects.all().delete()


def anonymize():
    if not util.is_enabled():
        raise Exception(
            "Will not run unless DEBUG or DEIDENTIFY_ALLOW_WITHOUT_DEBUG is True"
        )

    policy = build_policy()
    for (_, model), model_policy in policy.model_policies.items():
        if isinstance(model_policy, ObscureFields):
            validate_field_map(model, model_policy.field_map)

    all_tables = list(enumerate_tables())

    for app, model in enumerate_models():
        for table in [model._meta.db_table, *enumerate_unmanaged_tables(model)]:
            if table in all_tables:
                all_tables.remove(table)

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
                anonymize_model(model, model_policy.field_map)

            if model_policy.post_action:
                logger.info("Running post action %s:%s", app, model)
                model_policy.post_action()

            continue

    for table in enumerate_database_cache_tables():
        if table in all_tables:
            all_tables.remove(table)
        logger.info("Truncating cache table %s", table)
        truncate_table(table)

    # Django owns its migration ledger; it holds no user data.
    if "django_migrations" in all_tables:
        all_tables.remove("django_migrations")

    if len(all_tables):
        logger.warning("Unhandled tables: %s", all_tables)
