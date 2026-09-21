from django.conf import settings
from django.core import management
from django.core.management.base import BaseCommand, CommandError

from deidentify.actions import anonymize


class Command(BaseCommand):
    help = "Anonymize the current database in place, per the configured policy."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Will not run unless DEBUG is True")

        management.call_command("migrate")
        anonymize()
