from django.test import TestCase, override_settings

from deidentify.model_actions import NoAction, TruncateTable
from deidentify.policy import build_policy, merge_anonymizer_field_map
from tests.testapp.models import Secret


class AnonymizerFieldMapMergeTests(TestCase):
    """`_anonymizer_field_map` merges across the MRO so a subclass that declares
    its own map extends — never silently replaces — its bases' maps.

    Uses plain Python classes: the merge is pure attribute resolution and needs
    no Django models, keeping this suite free of any domain-app dependency.
    """

    def test_empty_subclass_inherits_base_map(self):
        class Base:
            _anonymizer_field_map = {"name": "x"}

        class Sub(Base):
            pass

        self.assertEqual(merge_anonymizer_field_map(Sub), {"name": "x"})

    def test_subclass_extends_base_map(self):
        class Base:
            _anonymizer_field_map = {"name": "x"}

        class Sub(Base):
            _anonymizer_field_map = {"email": "y"}

        self.assertEqual(merge_anonymizer_field_map(Sub), {"name": "x", "email": "y"})

    def test_most_derived_wins_for_shared_key(self):
        class Base:
            _anonymizer_field_map = {"shared": "base", "only_base": "b"}

        class Sub(Base):
            _anonymizer_field_map = {"shared": "sub", "only_sub": "s"}

        merged = merge_anonymizer_field_map(Sub)
        self.assertEqual(merged["shared"], "sub")  # subclass overrides
        self.assertEqual(merged["only_base"], "b")  # base entry preserved
        self.assertEqual(merged["only_sub"], "s")

    def test_multi_level_inheritance_accumulates(self):
        class A:
            _anonymizer_field_map = {"a": 1}

        class B(A):
            _anonymizer_field_map = {"b": 2}

        class C(B):
            _anonymizer_field_map = {"c": 3}

        self.assertEqual(merge_anonymizer_field_map(C), {"a": 1, "b": 2, "c": 3})

    def test_class_without_any_map(self):
        class Plain:
            pass

        self.assertEqual(merge_anonymizer_field_map(Plain), {})


class ConfidentialTableDispatchTests(TestCase):
    """Regression test: build_policy() must store *instances* of the action
    classes, not the classes themselves — actions.anonymize() dispatches with
    isinstance(), so a class-valued entry silently falls through and the model
    is never truncated. Fails against the pre-fix code (build_policy assigned
    the bare `TruncateTable` class for TRUNCATE_TABLE policies).
    """

    def test_confidential_table_model_gets_a_truncate_table_instance(self):
        policy = build_policy()
        action = policy.model_policies[("tests.testapp", Secret)]
        self.assertIsInstance(action, TruncateTable)
        self.assertNotEqual(action, TruncateTable)  # not the bare class


def _policy_hook_for_test(policy):
    policy.model_policies[("some_app", object)] = NoAction()


class PolicyHookTests(TestCase):
    """DEIDENTIFY_POLICY_HOOK lets a project register policies for third-party
    apps (social_django, django_otp, ...) without the library importing them.
    """

    @override_settings(DEIDENTIFY_POLICY_HOOK="tests.test_policy._policy_hook_for_test")
    def test_hook_is_invoked_and_can_add_policies(self):
        policy = build_policy()
        self.assertIsInstance(policy.model_policies[("some_app", object)], NoAction)

    def test_hook_setting_absent_is_a_noop(self):
        # No DEIDENTIFY_POLICY_HOOK configured in tests/settings.py — build_policy
        # must not raise just because the hook is unset.
        build_policy()
