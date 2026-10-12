# Plan: SQL-side anonymization

## Problem

`anonymize_model` pulls every row of a table into Python, runs faker on each column, and writes
the rows back with `bulk_update` in 20,000-row chunks.

- **Memory:** large `TextField`/JSON columns × 20k rows, plus one giant `CASE WHEN` UPDATE.
  On the key worker pod this got OOM-killed (exit 137) partway through `PhaseOneIllustration`.
- **Speed:** with a remote database (RDS), the time goes into network round trips and Python
  work. A local Postgres hides this.

## Goal

When a field-map value can be computed in SQL, anonymize the column with one `UPDATE`, so no
rows come back to Python. Callables keep working as they do today.

## Design

### 1. New field-map value form: Django `Expression`

`FIELD_MAPPING_VALUE` gains `django.db.models.expressions.Combinable` (`F`, `Value`, `Func`,
`Concat`, `RawSQL`, `Case`, …).

```python
_anonymizer_field_map = {
    "email": Concat(Value("user"), F("id"), Value("@example.com")),
    "home_phone": "(999) 999-9999",          # literal: SQL path
    "notes": lambda f: f.sentence,           # callable: Python path
}
```

### 2. `anonymize_model` splits the columns

- **SQL columns** (an expression, or a literal `str` / `int` / `None`): one
  `model.objects.update(**{col: guarded(expr)})`.
  - `guarded(col, expr)` = `Case(When(<col is truthy>, then=expr), default=F(col))`, which keeps
    today's `if value:` behaviour (null and empty values stay as they are). "Truthy" means
    `isnull=False` and, for string fields, `!= ""`.
- **Callable columns:** today's loop, with these changes:
  - chunk size taken from the `DEIDENTIFY_CHUNK_SIZE` setting (default **2000**, was 20000)
  - `bulk_update(..., batch_size=chunk_size)`
  - `.only("pk", *callable_columns)`, so SQL-path columns aren't loaded
- Run the SQL path first, then the Python path. A model with only SQL columns never iterates its
  rows.

### 3. Optional pk-range batching for the SQL path

One huge UPDATE means a long transaction and a WAL spike on RDS. Add a
`DEIDENTIFY_UPDATE_BATCH_SIZE` setting (default `None` = single statement). When it's set, loop
`qs.filter(pk__gte=lo, pk__lt=hi).update(...)` over `min(pk)` to `max(pk)`. Log progress per
batch, as the Python path does today.

### 4. Helpers module: `deidentify/sql.py`

Ready-made expressions, so consuming apps don't each write their own:

| helper | SQL | backend |
|---|---|---|
| `fake_choice(fake_fn, n=1000)` | `(ARRAY[%s,…])[1 + id % n]`. The pool is built once from faker, so values still look realistic. | Postgres |
| `seq_email(prefix="user", domain="example.com")` | `prefix \|\| id \|\| '@' \|\| domain` | any |
| `seq_text(prefix)` | `prefix \|\| ' ' \|\| id` | any |
| `seq_digits(width)` | `lpad(id::text, width, '0')`, unique per row | any (`LPad`) |
| `jsonb_set_keys(col, **kv)` | `COALESCE((pg_temp.try_jsonb(col) \|\| jsonb_build_object(...))::text, '{}')` | Postgres 9.5+ |

- `fake_choice` and `jsonb_set_keys` are Postgres-only. Document that, and skip their tests
  unless `DEIDENTIFY_TEST_POSTGRES` is set.
- `jsonb_set_keys`: invalid JSON becomes `'{}'`, matching key's current
  `anonymize_glp_illustration` fallback. Before using it, `anonymize_model` runs this once per
  connection. It lasts only for the session, so it needs no migration and leaves nothing behind:
  ```sql
  CREATE OR REPLACE FUNCTION pg_temp.try_jsonb(t text) RETURNS jsonb AS $$
  BEGIN RETURN t::jsonb; EXCEPTION WHEN others THEN RETURN NULL; END $$ LANGUAGE plpgsql;
  ```
  Functions in `pg_temp` must be called with the schema name (`pg_temp.try_jsonb`). The
  exception block costs one subtransaction per row, which is negligible next to the round trips
  it removes.

### 5. Multi-table inheritance

`QuerySet.update()` on a child model works only when every updated column is on the child's own
table. When a column lives on the parent table, run `update()` on the parent model, filtered to
`pk__in=child pks` (a subquery, so it still runs entirely in the DB). Group the SQL columns by
`field.model`.

## Tests (`tests/test_actions.py`, sqlite unless marked)

1. A literal column is updated, and null/blank rows are left alone.
2. An expression column (`Concat(Value("u"), F("id"))`) is updated in SQL. Assert no per-row
   SELECT by checking the query count with `CaptureQueriesContext`: it stays constant as rows
   are added.
3. A model mixing an expression column and a callable column: both are applied, and the Python
   path loads only the callable columns.
4. Multi-table inheritance: an expression on a parent-table field and on a child-table field
   (add a child model to `tests/testapp`).
5. `DEIDENTIFY_CHUNK_SIZE` / `DEIDENTIFY_UPDATE_BATCH_SIZE` are respected.
6. (Postgres only) `fake_choice`, `jsonb_set_keys`, including that invalid JSON becomes `{}`.
7. Existing tests and the snapshot test still pass unchanged (backwards compatible).

## Docs

- README: a new "SQL expressions" section on the value forms, guard semantics, helpers, and the
  two settings.
- AGENTS.md: mention `sql.py` in the architecture list.

## Consumer migration (key repo, after install)

| model.field | new value |
|---|---|
| `PhaseOneIllustration.raw_data`, `PhaseTwoIllustration.raw_data` | `jsonb_set_keys("raw_data", first_name="", last_name="", illustration_name=seq_text("Illustration"))` |
| `*first_name`, `*last_name`, `city`, `company` | `fake_choice(lambda f: f.first_name)` etc. |
| `*email` | `seq_email()` |
| `ssn` | `seq_digits(9)` |
| `notes`, `note`, `name`, `illustration name` | `seq_text("Note")` / `fake_choice(lambda f: f.sentence)` |
| `date_of_birth` | `Func(F("date_of_birth"), …)`: Jan 1 of the same year |
| `account_no`, `policy_number` | `seq_digits(n)`; check what format `fake_glp_policy_no` needs first |
| phone literals | unchanged; they move to the SQL path automatically |

Install in key with:
`uv add "django-deidentify @ git+https://github.com/joelryan2k/django-deidentify.git@<branch>"`
(or `uv add --editable ~/dev/iw/django-deidentify` for local testing).

## Out of scope

- Removing the callable path. It stays for anything that really needs Python.
- Automatic `VACUUM ANALYZE`. Document it as a recommended step after the run.
