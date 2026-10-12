## What this is

Fail-closed database de-identification for Django. Every model in every installed app must
declare a policy (mixin) or `anonymize()` raises `Missing policy for ...`. This is the core
design invariant — new PII fields/models fail loud instead of silently leaking into a scrubbed
dump. See README.md for the full usage story (mixins, `_anonymizer_field_map` value forms,
`DEIDENTIFY_POLICY_HOOK` for third-party models like `django.contrib.auth.User`).

## Commands

Environment is managed by devbox + uv (Python 3.14, see `devbox.json`).

```
devbox shell              # enters env, runs `uv sync --extra test` + activates .venv
devbox run test           # == pytest
pytest                    # once inside the devbox shell / venv
pytest tests/test_actions.py::test_name   # single test
```

Postgres-only tests (`util.truncate_table`, `enumerate_tables`) are skipped unless
`DEIDENTIFY_TEST_POSTGRES` is set, in which case they hit `$PGDATABASE`/`$PGHOST`/etc (libpq env
vars). All other tests run on in-memory sqlite (`tests/settings.py`).

No configured lint/format/typecheck command exists in this repo currently.

## Architecture

Five modules, each with one job, called in this order by `deidentify management command` →
`actions.anonymize()`:

- **`mixins.py`** — `NotConfidential` / `ConfidentialFields` / `ConfidentialTable`, the only
  public API models touch. Each sets `_anonymizer_policy` (an `AnonymizerModelPolicy` enum).
  `ConfidentialFields` additionally carries `_anonymizer_field_map: FIELD_MAPPING`.
- **`policy.py`** — `build_policy()` walks every installed app's models
  (`util.enumerate_models`), reads `_anonymizer_policy` off each, and builds an
  `AnonymizerPolicy.model_policies` dict keyed by `(app_label, model_class)` →
  `model_actions.{NoAction,TruncateTable,ObscureFields}`. `merge_anonymizer_field_map()` walks
  the MRO base-first so a subclass's own `_anonymizer_field_map` *extends* (not replaces) its
  bases' maps — an inherited redaction can't be silently dropped. After scanning, it calls
  `settings.DEIDENTIFY_POLICY_HOOK` (a dotted import path) once with the in-progress policy, for
  registering third-party/contrib models that can't carry a mixin.
- **`model_actions.py`** — plain data classes for the three action types (`NoAction`,
  `TruncateTable`, `ObscureFields(field_map, post_action)`). No behavior lives here.
- **`actions.py`** — `anonymize()` is the entry point: builds the policy, then for every model
  either skips it, truncates its table (`Model.objects.all().delete()`), or rewrites fields
  (`anonymize_model`). Field maps hold only literals and Django expressions; `anonymize()`
  checks every map with `validate_field_map()` before touching any table, so a callable fails
  the run up front. `anonymize_model` runs one `UPDATE` per concrete table (grouped by
  `field.model` for multi-table inheritance), each value wrapped by `guarded()` so null and
  empty values are left alone. After processing all known models, any DB table not backed by a model (from
  `util.enumerate_tables`, Postgres `information_schema`) is logged as `Unhandled tables` — a
  secondary signal for policy drift, not currently fail-closed itself.
- **`sql.py`** — expression helpers for field maps (`seq_text`, `seq_email`, `seq_digits`, and
  the PostgreSQL-only `fake_choice`, `fake_date` and `jsonb_set_keys`). `ensure_functions()` creates the
  session-scoped `pg_temp.try_jsonb_object()` that `jsonb_set_keys` relies on.
- **`util.py`** — `enumerate_models`/`enumerate_tables` (DB introspection) and
  `truncate_table`.

Everything guards `settings.DEBUG` (overridable via `DEIDENTIFY_ALLOW_WITHOUT_DEBUG`) and refuses to run otherwise — this tool is meant to run only
against a disposable local/dev database copy, never against production data in place.

`tests/testapp/models.py` is the fixture app exercising all three mixins and the field-map
value forms (including the abstract-base MRO-merge case); `tests/hooks.py` has the test-only
`DEIDENTIFY_POLICY_HOOK` that fills remaining apps (auth, contenttypes, sessions) with
`NoAction` so the "missing policy" guard doesn't fire on apps outside the thing under test.
