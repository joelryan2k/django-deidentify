# django-deidentify

Fail-closed database de-identification for Django. Every model in every
installed app must declare a policy — or `anonymize()` raises. New PII fails
loud instead of leaking into an exported dump.

Meant for scrubbing a production database copy (restore it locally, run this,
re-dump it) into something safe to hand to a contractor, load into a dev
environment, or attach to a bug report.

If you just want to scrub a handful of known fields and don't need the
"every model must be accounted for" guarantee, look at
[django-scrubber](https://pypi.org/project/django-scrubber/) instead — it's
opt-in rather than fail-closed, which is less work to adopt on a small app.

## Install

```
pip install django-deidentify
```

Add to `INSTALLED_APPS`, typically only in dev/CI settings:

```python
if DEBUG:
    INSTALLED_APPS.append("deidentify")
```

## Usage

Every model picks exactly one mixin:

```python
from django.db.models import Value
from django.db.models.functions import Concat

from deidentify.mixins import ConfidentialFields, ConfidentialTable, NotConfidential
from deidentify.sql import fake_choice, seq_digits, seq_email


class Order(NotConfidential, models.Model): ...  # no PII, left untouched


class Session(ConfidentialTable, models.Model): ...  # table is emptied entirely


class Customer(ConfidentialFields, models.Model):
    first_name = models.CharField(max_length=100)
    email = models.EmailField()
    account_number = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=20)

    _anonymizer_field_map = {
        "first_name": fake_choice(lambda f: f.first_name),
        "email": seq_email(),
        "account_number": Concat(Value("A"), seq_digits(8)),  # unique: built from the pk
        "phone": "(999) 999-9999",
    }
```

`_anonymizer_field_map` values are either a plain literal (`str`, `int`, `float`, `None`) or a
Django expression (`F`, `Value`, `Concat`, `Func`, …). Anything else, such as a callable, raises
`TypeError` before any table is changed.

Each table is anonymized with one `UPDATE`, so no rows are loaded into Python. The new value only
replaces values that are present: nulls and empty strings are left as they are.

`deidentify.sql` provides ready-made expressions:

| helper | result | backend |
|---|---|---|
| `seq_text("Note")` | `Note <pk>` | any |
| `seq_email(prefix="user", domain="example.com")` | `user<pk>@example.com` | any |
| `seq_digits(9)` | pk zero-padded to 9 digits | any |
| `fake_choice(lambda f: f.first_name, n=5000, locales=None)` | picks from a pool of up to `n` unique faker values, chosen per row by a salted hash of the pk (so two `fake_choice` columns vary independently). The pool is built once per run; no faker call happens per row. | PostgreSQL |
| `fake_date(date(1940, 1, 1), date(2000, 12, 31))` | a date in the range, chosen per row by a salted hash of the pk | PostgreSQL |
| `jsonb_set_keys("raw_data", first_name="", name=seq_text("Plan"))` | sets keys in a JSON text column; anything that isn't a JSON object (invalid JSON, arrays, scalars) becomes `{}` | PostgreSQL |

Settings:
- `DEIDENTIFY_UPDATE_BATCH_SIZE` (default `None`, meaning one statement): splits each
  `UPDATE` into pk ranges of this size, to keep transactions and WAL small. Requires
  integer primary keys.

After a large run, consider `VACUUM ANALYZE`.

A subclass's `_anonymizer_field_map` **extends**, not replaces, its base
classes' maps — an inherited redaction can't be silently dropped by a
subclass that forgets to re-list it.

Then run:

```
python manage.py deidentify
```

This runs `migrate` and `anonymize()` against the current database, in
place, guarded by `settings.DEBUG` (it refuses to run otherwise). To run without
`DEBUG` (e.g. a CI/staging job on a disposable copy), set
`DEIDENTIFY_ALLOW_WITHOUT_DEBUG = True`. Getting a
production dump in beforehand and exporting the scrubbed result afterward is
your project's job — wrap this command with your own restore/dump steps.

### Third-party and contrib models

Models you don't own (`django.contrib.auth.User`, `rest_framework.authtoken`,
`social_django`, ...) can't carry a mixin. Register their policies from a
settings hook instead:

```python
# settings.py
DEIDENTIFY_POLICY_HOOK = "myproject.deidentify_hooks.add_policies"
```

```python
# myproject/deidentify_hooks.py
import django.contrib.auth.models
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX

from deidentify.model_actions import NoAction, ObscureFields, TruncateTable


def add_policies(policy):
    policy.model_policies[("django.contrib.auth", django.contrib.auth.models.User)] = (
        ObscureFields({"password": UNUSABLE_PASSWORD_PREFIX}, None)
    )
```

The hook is called once, after model scanning, with the in-progress
`AnonymizerPolicy` — mutate `policy.model_policies` directly.

## License

MIT
