from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


@override_settings(DEBUG=False)
class DebugGuardTests(TestCase):
    def test_refuses_without_debug(self):
        with self.assertRaises(CommandError):
            call_command("deidentify_snapshot", input="in.dump", output="out.dump")

    @override_settings(DEIDENTIFY_ALLOW_WITHOUT_DEBUG=True)
    @mock.patch("deidentify.management.commands.deidentify_snapshot.subprocess.run")
    @mock.patch("deidentify.management.commands.deidentify_snapshot.anonymize")
    def test_runs_with_override_setting(self, mock_anonymize, mock_run):
        call_command("deidentify_snapshot", input="in.dump", output="out.dump")
        mock_anonymize.assert_called_once()


@override_settings(DEBUG=True)
class AnonymizeSnapshotTests(TestCase):
    @mock.patch("deidentify.management.commands.deidentify_snapshot.subprocess.run")
    @mock.patch("deidentify.management.commands.deidentify_snapshot.anonymize")
    def test_restores_then_anonymizes_then_dumps(self, mock_anonymize, mock_run):
        call_command("deidentify_snapshot", input="in.dump", output="out.dump")

        restore_call, dump_call = mock_run.call_args_list
        self.assertEqual(
            restore_call.args[0], ["devbox", "run", "restore-database", "in.dump"]
        )
        self.assertEqual(dump_call.args[0][-1], "out.dump")
        mock_anonymize.assert_called_once()
