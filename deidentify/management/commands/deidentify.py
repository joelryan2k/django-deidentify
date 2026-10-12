from deidentify import util
from django.core import management
from django.core.management.base import BaseCommand, CommandError

from deidentify.actions import anonymize


class Command(BaseCommand):
    help = "Anonymize the current database in place, per the configured policy."

    def handle(self, *args, **options):
        if not util.is_enabled():
            raise CommandError("Will not run unless DEBUG or DEIDENTIFY_ALLOW_WITHOUT_DEBUG is True")

        management.call_command("migrate")
        anonymize()
