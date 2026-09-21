from django.test import TestCase

from deidentify.util import create_incrementing_faker


class IncrementingFakerTests(TestCase):
    def test_increments_and_formats_each_call(self):
        mapping_fn = create_incrementing_faker(20000, "A{:05d}")
        fn = mapping_fn(fake=None)
        self.assertEqual(fn(), "A20000")
        self.assertEqual(fn(), "A20001")
