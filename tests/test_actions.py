import os
import unittest

from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from deidentify.actions import anonymize, anonymize_model, truncate_model
from deidentify.model_actions import TruncateTable
from deidentify.policy import build_policy
from deidentify.util import enumerate_tables, truncate_table
from tests.testapp.models import ChildWithOwnSecret, Secret

postgres_only = unittest.skipUnless(
    os.environ.get("DEIDENTIFY_TEST_POSTGRES"),
    "requires DEIDENTIFY_TEST_POSTGRES and a local Postgres",
)


@override_settings(DEBUG=True)
class DispatchAndFieldMappingTests(TestCase):
    """Exercises build_policy() + the per-action dispatch pieces directly
    (rather than the full anonymize() orchestrator, whose "unhandled tables"
    warning needs Postgres's information_schema) against tests/testapp's
    models — sqlite-portable.
    """

    def test_confidential_table_rows_are_deleted(self):
        """Regression: build_policy() must yield a TruncateTable *instance*
        (actions dispatch with isinstance()), or these rows never get emptied.
        """
        Secret.objects.create()
        Secret.objects.create()

        policy = build_policy()
        action = policy.model_policies[("tests.testapp", Secret)]
        self.assertIsInstance(action, TruncateTable)
        truncate_model(Secret)

        self.assertEqual(Secret.objects.count(), 0)

    def test_inherited_field_map_merges_with_subclass_map(self):
        row = ChildWithOwnSecret.objects.create(
            name="Jane Q Client", note="secret note"
        )

        policy = build_policy()
        mapping = policy.model_policies[("tests.testapp", ChildWithOwnSecret)].field_map
        anonymize_model(ChildWithOwnSecret, mapping)

        row.refresh_from_db()
        self.assertNotEqual(row.name, "Jane Q Client")  # inherited redaction
        self.assertNotEqual(row.note, "secret note")  # own redaction


@postgres_only
@override_settings(
    DEBUG=True, DEIDENTIFY_POLICY_HOOK="tests.hooks.default_remaining_to_no_action"
)
class AnonymizeEndToEndTests(TestCase):
    """The full anonymize() pipeline, including the Postgres-only
    unhandled-tables warning — needs a real Postgres database.
    """

    def test_runs_and_empties_confidential_tables(self):
        Secret.objects.create()

        anonymize()

        self.assertEqual(Secret.objects.count(), 0)


@postgres_only
class TruncateTableUtilTests(TransactionTestCase):
    """
    Tests for deidentify.util.truncate_table / enumerate_tables.

    Uses django_session because it has no inbound FK constraints, matching the
    real calling pattern — anonymize() truncates leaf tables (sessions, tokens,
    log entries) that nothing else references. Postgres-only: TRUNCATE and
    information_schema aren't portable to sqlite.
    """

    def _make_session(self):
        from django.contrib.sessions.models import Session

        Session.objects.create(
            session_key="testsession1234567890123456789012",
            session_data="{}",
            expire_date=timezone.now(),
        )

    def test_truncates_table_by_name(self):
        from django.contrib.sessions.models import Session

        self._make_session()
        self.assertEqual(Session.objects.count(), 1)
        truncate_table("django_session")
        self.assertEqual(Session.objects.count(), 0)

    def test_truncates_already_empty_table(self):
        """Truncating an empty table must not raise."""
        truncate_table("django_session")

    def test_enumerate_tables_lists_known_table(self):
        self.assertIn("django_session", list(enumerate_tables()))
