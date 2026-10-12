import json
import os
import unittest

import faker
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from deidentify.actions import anonymize_model
from deidentify.policy import build_policy
from deidentify.sql import fake_choice
from tests.testapp.models import ConcreteChild, JsonRow, SqlRow

postgres_only = unittest.skipUnless(
    os.environ.get("DEIDENTIFY_TEST_POSTGRES"),
    "requires DEIDENTIFY_TEST_POSTGRES and a local Postgres",
)


def run(model, mapping=None):
    if mapping is None:
        mapping = build_policy().model_policies[("tests.testapp", model)].field_map
    anonymize_model(model, faker.Faker(), mapping)


@override_settings(DEBUG=True)
class SqlPathTests(TestCase):
    def test_literals_and_expressions_are_applied(self):
        row = SqlRow.objects.create(label="Jane", email="jane@real.com", digits="123456789", note="secret")

        run(SqlRow)

        row.refresh_from_db()
        self.assertEqual(row.label, "REDACTED")
        self.assertEqual(row.email, f"user{row.pk}@example.com")
        self.assertEqual(row.digits, str(row.pk).zfill(9))
        self.assertNotEqual(row.note, "secret")

    def test_blank_and_null_values_are_left_alone(self):
        row = SqlRow.objects.create(label=None, email="", digits="", note="")

        run(SqlRow)

        row.refresh_from_db()
        self.assertIsNone(row.label)
        self.assertEqual((row.email, row.digits, row.note), ("", "", ""))

    def test_sql_only_mapping_does_not_load_rows(self):
        mapping = {"label": "REDACTED", "email": SqlRow._anonymizer_field_map["email"]}

        def query_count(rows):
            SqlRow.objects.bulk_create(SqlRow(label="x", email="x") for _ in range(rows))
            with CaptureQueriesContext(connection) as ctx:
                run(SqlRow, mapping)
            return len(ctx.captured_queries)

        self.assertEqual(query_count(3), query_count(300))
        self.assertEqual(SqlRow.objects.exclude(label="REDACTED").count(), 0)

    def test_multi_table_inheritance_updates_both_tables(self):
        child = ConcreteChild.objects.create(name="Jane", secret="shh")

        run(ConcreteChild)

        child.refresh_from_db()
        self.assertEqual(child.name, f"Parent {child.pk}")
        self.assertEqual(child.secret, f"Secret {child.pk}")

    @override_settings(DEIDENTIFY_UPDATE_BATCH_SIZE=2)
    def test_batched_updates_cover_every_row(self):
        SqlRow.objects.bulk_create(SqlRow(label="x") for _ in range(5))

        run(SqlRow, {"label": "REDACTED"})

        self.assertEqual(SqlRow.objects.filter(label="REDACTED").count(), 5)

    @override_settings(DEIDENTIFY_CHUNK_SIZE=2)
    def test_python_path_respects_chunk_size(self):
        SqlRow.objects.bulk_create(SqlRow(note="secret") for _ in range(5))

        run(SqlRow, {"note": lambda f: lambda: "fake"})

        self.assertEqual(SqlRow.objects.filter(note="fake").count(), 5)


@postgres_only
@override_settings(DEBUG=True)
class PostgresHelperTests(TestCase):
    def test_jsonb_set_keys(self):
        row = JsonRow.objects.create(raw_data=json.dumps({"first_name": "Jane", "age": 50}))

        run(JsonRow)

        row.refresh_from_db()
        self.assertEqual(
            json.loads(row.raw_data),
            {"first_name": "", "age": 50, "illustration_name": f"Illustration {row.pk}"},
        )

    def test_jsonb_set_keys_replaces_invalid_json(self):
        row = JsonRow.objects.create(raw_data="not json")

        run(JsonRow)

        row.refresh_from_db()
        self.assertEqual(row.raw_data, "{}")

    def test_fake_choice(self):
        row = SqlRow.objects.create(label="Jane")

        run(SqlRow, {"label": fake_choice(lambda f: f.first_name, n=10)})

        row.refresh_from_db()
        self.assertNotIn(row.label, ("Jane", ""))
