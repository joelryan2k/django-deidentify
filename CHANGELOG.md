# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/);
while the version is 0.x, breaking changes bump the minor version.

## [0.2.0]

### Added

- Field-map values can be Django expressions (`F`, `Value`, `Concat`, `Func`, …). Each table is
  anonymized with one `UPDATE`, so no rows are loaded into Python.
- `deidentify.sql` helpers: `seq_text`, `seq_email`, `seq_digits`, and the PostgreSQL-only
  `fake_choice` (with `n`, `seed` and `locales`), `fake_date` and `jsonb_set_keys` (anything that
  isn't a JSON object, including invalid JSON, arrays and scalars, becomes `{}`).
- Setting `DEIDENTIFY_UPDATE_BATCH_SIZE` (default `None`).

### Removed (breaking)

- **Callable field-map values.** 1-arg (`lambda f: ...`) and 2-arg (`lambda f, previous: ...`)
  callables are no longer supported; `anonymize()` raises `TypeError` naming the model and column
  before changing anything.
- **`create_incrementing_faker` and `create_incrementing_faker_function`** (`deidentify.util`).
- **The `fake` argument of `anonymize_model`.** It is now `anonymize_model(model, mapping)`.

### Changed (breaking)

- **Literal values run as SQL.** Only null and empty-string values are skipped. Before, any falsy
  value (`0`, `False`, `[]`) was skipped as well.
- **Rows hidden by a custom default manager are now anonymized.** The library used
  `Model.objects`; it now uses `Model._base_manager`, so a default manager that filters rows
  (e.g. soft-deleted or inactive rows) no longer stops those rows from being scrubbed.
- **On PostgreSQL, the run creates a temporary function** (`pg_temp.try_jsonb_object`) on its
  connection. The database user needs the `TEMP` privilege, which PostgreSQL grants by default.

## Upgrading from 0.1.x

1. Bump the dependency to `0.2.0`.
2. Replace every callable in `_anonymizer_field_map` (and in `ObscureFields(...)` maps registered
   from `DEIDENTIFY_POLICY_HOOK`) with a literal or an expression. Running `deidentify` lists
   the first one it finds.

   | before | after |
   |---|---|
   | `lambda f: f.first_name` | `fake_choice(lambda f: f.first_name)` (PostgreSQL) |
   | `lambda f: f.email` | `seq_email()` |
   | `lambda f: lambda: f.ssn().replace("-", "")` | `seq_digits(9)` |
   | `lambda f: f.sentence` | `seq_text("Note")` or `fake_choice(lambda f: f.sentence)` |
   | `lambda f: f.phone_number` | a literal such as `"(999) 999-9999"` |
   | `lambda f: f.date_of_birth` | `fake_date(date(1940, 1, 1), date(2000, 12, 31))` (PostgreSQL) |
   | `create_incrementing_faker(20000, "A{:05d}")` | `Concat(Value("A"), seq_digits(5))` (unique per pk) |
   | 2-arg callable that rewrites JSON text | `jsonb_set_keys("col", key=value)` (PostgreSQL) |

   A 2-arg callable that derived the new value from the old one needs a SQL expression over
   `F("<column>")`.
3. Check field maps for literals on columns where falsy non-empty values (`0`, `False`) must be
   preserved. Those values are now replaced.
4. Check models whose default manager filters rows. Those rows are now anonymized too, which is
   usually what you want.
5. On PostgreSQL, if the database user has had `TEMP` revoked, grant it
   (`GRANT TEMP ON DATABASE <db> TO <user>`).
6. For large tables on a remote database, consider `DEIDENTIFY_UPDATE_BATCH_SIZE = 50000` to keep
   transactions small (requires integer primary keys), and run `VACUUM ANALYZE` after the run.

## [0.1.0]

Initial release.
