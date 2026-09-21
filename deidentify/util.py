from django.apps import apps
from django.db import connection


def enumerate_models():
    for app in apps.get_app_configs():
        for model in app.get_models():
            yield app, model


def enumerate_tables():
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'"""
        )

        for table in cursor.fetchall():
            yield table[0]


def truncate_table(table_name: str):
    with connection.cursor() as cursor:
        cursor.execute(f"""TRUNCATE TABLE {connection.ops.quote_name(table_name)}""")


def create_incrementing_faker_function(start: int = 1, format_str: str = "{}"):
    """Build a callable that returns incrementing formatted values.

    For unique-constrained columns (e.g. account numbers), where a random fake
    value risks a collision but a per-column counter never does.

    Args:
        start: Starting value for the counter
        format_str: Format string with a ``{}`` placeholder for the counter

    Returns:
        A callable that returns the next formatted value each time it's called
    """

    def faker_function():
        nonlocal start
        value = format_str.format(start)
        start += 1
        return value

    return faker_function


def create_incrementing_faker(start: int = 1, format_str: str = "{}"):
    """A 1-arg field-mapping value: ``_anonymizer_field_map = {"acct": create_incrementing_faker(20000, "A{:05d}")}``."""
    fn = create_incrementing_faker_function(start, format_str)

    def mapping_fn(fake):
        return fn

    return mapping_fn
