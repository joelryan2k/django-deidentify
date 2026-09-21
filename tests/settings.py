import os

DEBUG = True
SECRET_KEY = "test"
USE_TZ = True

# Most tests run fine on sqlite. The two Postgres-only tests (util.truncate_table,
# enumerate_tables) are skipped unless DEIDENTIFY_TEST_POSTGRES is set, in which case
# they run against $PGDATABASE/$PGHOST/etc (libpq env vars, left blank = local defaults).
if os.environ.get("DEIDENTIFY_TEST_POSTGRES"):
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql"}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "deidentify",
    "tests.testapp",
]
