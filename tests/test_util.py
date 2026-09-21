from django.test import TestCase, override_settings

from deidentify.util import create_incrementing_faker, enumerate_database_cache_tables


class IncrementingFakerTests(TestCase):
    def test_increments_and_formats_each_call(self):
        mapping_fn = create_incrementing_faker(20000, "A{:05d}")
        fn = mapping_fn(fake=None)
        self.assertEqual(fn(), "A20000")
        self.assertEqual(fn(), "A20001")


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
