# deidentify — usage guide for agents

You're reading this because you're working in a project that has `django-deidentify`
installed. This file ships inside the package itself so it's here in `site-packages`
even if you never open the library's own repo.

Fail-closed DB scrubbing for Django: every model in every installed app must declare a
policy, or `anonymize()` raises `Missing policy for ...`. New PII fields fail loud
instead of leaking into a scrubbed dump.

## Adding a policy to a model

Every model picks exactly one mixin from `deidentify.mixins`:

```python
from django.db.models import Value
from django.db.models.functions import Concat

from deidentify.mixins import ConfidentialFields, ConfidentialTable, NotConfidential
from deidentify.sql import seq_digits, seq_email


class Order(NotConfidential, models.Model): ...  # no PII, left untouched


class Session(ConfidentialTable, models.Model): ...  # table is emptied entirely


class Customer(ConfidentialFields, models.Model):
    email = models.EmailField()
    account_number = models.CharField(max_length=20, unique=True)

    _anonymizer_field_map = {
        "email": seq_email(),
        "account_number": Concat(Value("A"), seq_digits(8)),  # unique: built from the pk
    }
```

`_anonymizer_field_map` values are plain literals or Django expressions; each table is
anonymized with one SQL `UPDATE`. Callables are not supported and fail the run up front with
`TypeError`. A subclass's map **extends**, not replaces, its bases' maps.

`deidentify.sql` has ready-made expressions: `seq_text`, `seq_email`, `seq_digits`, and on
PostgreSQL `fake_choice(lambda f: f.first_name, locales=[...])` (a faker pool built once per
run, not per row), `fake_date(start, end)` and `jsonb_set_keys("col", key=value)`. See
`CHANGELOG.md` in the library repo for 0.1 → 0.2 upgrade notes.

## Models you don't own

`django.contrib.auth.User`, DRF's `Token`, third-party app models, etc. can't carry a
mixin — register them from the project's `DEIDENTIFY_POLICY_HOOK` (a dotted settings
path to a `add_policies(policy)` callable), not in this package. Find that hook module
in the current project (commonly `<project>/anonymize_policy.py` or similar, referenced
from `settings.py`) before assuming a model's policy is missing — it's likely handled
there rather than via a mixin.

## Diagnosing "Missing policy for X" errors

This is the library working as intended, not a bug. Fix it by adding a mixin to the
model (if you own it) or a `policy.model_policies[...]` entry in the project's
`DEIDENTIFY_POLICY_HOOK` callable (if you don't). Don't work around it by disabling
`DEBUG` or skipping the check — that's the fail-closed guarantee this library exists
for.

## Running it

`python manage.py deidentify` runs `migrate` then `anonymize()` against the *current*
database, in place, guarded by `settings.DEBUG` (or `DEIDENTIFY_ALLOW_WITHOUT_DEBUG`) — refuses otherwise. Only run this
against a disposable local/dev database, never production. Some projects wrap this in
their own management command (e.g. `deidentify_snapshot`) to add restore-in/dump-out
steps around it — check for one before assuming `deidentify` is the only entry point.

Full development docs (architecture, tests, contributing) live in the library's own
repo — this file only covers using it as a dependency.
