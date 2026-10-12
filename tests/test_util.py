from django.test import TestCase, override_settings

from deidentify.util import (
    enumerate_database_cache_tables,
    enumerate_unmanaged_tables,
)


class EnumerateDatabaseCacheTablesTests(TestCase):
    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "LOCATION": "default_cache",
            },
            "sessions": {
                "BACKEND": "django.core.cache.backends.db.DatabaseCache",
                "LOCATION": "session_cache",
            },
            "other": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
        }
    )
    def test_yields_only_database_backed_cache_tables(self):
        self.assertEqual(
            set(enumerate_database_cache_tables()), {"default_cache", "session_cache"}
        )

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    )
    def test_yields_nothing_without_a_database_cache(self):
        self.assertEqual(list(enumerate_database_cache_tables()), [])


class EnumerateUnmanagedTablesTests(TestCase):
    def test_yields_auto_created_through_tables(self):
        from django.contrib.auth.models import User

        self.assertEqual(
            set(enumerate_unmanaged_tables(User)),
            {"auth_user_groups", "auth_user_user_permissions"},
        )
