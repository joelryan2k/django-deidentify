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
from deidentify.mixins import ConfidentialFields, ConfidentialTable, NotConfidential

class Order(NotConfidential, models.Model):
    ...  # no PII, left untouched

class Session(ConfidentialTable, models.Model):
    ...  # table is emptied entirely

class Customer(ConfidentialFields, models.Model):
    first_name = models.CharField(max_length=100)
    email = models.EmailField()
    account_number = models.CharField(max_length=20, unique=True)

    _anonymizer_field_map = {
        "first_name": lambda f: f.first_name,          # faker method, 1-arg form
        "email": lambda f, previous: (lambda: f"user+{hash(previous)}@example.com"),
        "account_number": create_incrementing_faker(20000, "A{:05d}"),  # unique columns
    }
```

`_anonymizer_field_map` values can be:
- a 1-arg callable `lambda f: f.email` — called as `fn(fake)()`
- a 2-arg callable `lambda f, previous: ...` — called as `fn(fake, previous)()`, gets the old value
- a plain string literal

A subclass's `_anonymizer_field_map` **extends**, not replaces, its base
classes' maps — an inherited redaction can't be silently dropped by a
subclass that forgets to re-list it.

Then run:

```
python manage.py deidentify
```

This runs `migrate` and `anonymize()` against the current database, in
place, guarded by `settings.DEBUG` (it refuses to run otherwise). Getting a
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
from deidentify.model_actions import NoAction, ObscureFields, TruncateTable

def reset_user_passwords():
    for user in django.contrib.auth.models.User.objects.all():
        user.set_password("admin")
        user.save()

def add_policies(policy):
    policy.model_policies[("django.contrib.auth", django.contrib.auth.models.User)] = (
        ObscureFields({}, reset_user_passwords)
    )
```

The hook is called once, after model scanning, with the in-progress
`AnonymizerPolicy` — mutate `policy.model_policies` directly.

## License

MIT
