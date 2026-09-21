from deidentify.model_actions import NoAction
from deidentify.util import enumerate_models


def default_remaining_to_no_action(policy):
    """Test-only DEIDENTIFY_POLICY_HOOK: fills in NoAction for every installed
    model that a test doesn't otherwise care about (django.contrib.auth,
    contenttypes, sessions), so anonymize()'s "Missing policy" guard doesn't
    fire for apps outside the thing under test.
    """
    for app, model in enumerate_models():
        policy.model_policies.setdefault((app.name, model), NoAction())
