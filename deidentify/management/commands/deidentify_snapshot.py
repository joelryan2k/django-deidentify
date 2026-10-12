import subprocess

from django.conf import settings
from deidentify import util
from django.core import management
from django.core.management.base import BaseCommand, CommandError

from deidentify.actions import anonymize


class Command(BaseCommand):
    help = (
        "Restore a devbox snapshot, anonymize it per the configured policy, "
        "and dump the result. Assumes a devbox 'restore-database' task and a "
        "local Postgres reachable at -h localhost."
    )

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True, help="Snapshot to restore")
        parser.add_argument(
            "--output", required=True, help="Path for the anonymized dump"
        )

    def handle(self, *args, **options):
        if not util.is_enabled():
            raise CommandError("Will not run unless DEBUG or DEIDENTIFY_ALLOW_WITHOUT_DEBUG is True")

        subprocess.run(
            ["devbox", "run", "restore-database", options["input"]], check=True
        )
        management.call_command("migrate")
        anonymize()

        database = settings.DATABASES["default"]["NAME"]
        subprocess.run(
            [
                "pg_dump",
                "-h",
                "localhost",
                "--no-owner",
                "-Fc",
                database,
                "-f",
                options["output"],
            ],
            check=True,
        )
