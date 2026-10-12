# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/);
while the version is 0.x, breaking changes bump the minor version.

## [0.2.0]

### Added

- Field-map values can be Django expressions (`F`, `Value`, `Concat`, `Func`, …). Expressions and
  literals run inside the database as one `UPDATE` per table, so no rows are loaded into Python.
- `deidentify.sql` helpers: `seq_text`, `seq_email`, `seq_digits`, and the PostgreSQL-only
  `fake_choice` (with `n`, `seed` and `locales`) and `jsonb_set_keys`.
- Settings `DEIDENTIFY_CHUNK_SIZE` (default 2000) and `DEIDENTIFY_UPDATE_BATCH_SIZE` (default
  `None`).

### Changed (breaking)

- **Literal values now run as SQL.** A literal `str`, `int`, `float` or `None` in a field map is
  applied with `UPDATE`, not row by row. Only null and empty-string values are skipped. Before,
  any falsy value (`0`, `False`, `[]`) was skipped as well.
- **Rows hidden by a custom default manager are now anonymized.** The library used
  `Model.objects`; it now uses `Model._base_manager`, so a default manager that filters rows
  (e.g. soft-deleted or inactive rows) no longer stops those rows from being scrubbed.
- **Default chunk size dropped from 20,000 to 2,000** on the Python (callable) path, to limit
  memory use. Set `DEIDENTIFY_CHUNK_SIZE` to change it.
- **On PostgreSQL, the run now creates a temporary function** (`pg_temp.try_jsonb`) on its
  connection. The database user needs the `TEMP` privilege, which PostgreSQL grants by default.

## Upgrading from 0.1.x

1. Bump the dependency to `0.2.0`.
2. Check field maps for literals on columns where falsy non-empty values (`0`, `False`) must be
   preserved. Those values are now replaced; use a callable to keep the old behaviour.
3. Check models whose default manager filters rows. Those rows are now anonymized too, which is
   usually what you want.
4. On PostgreSQL, if the database user has had `TEMP` revoked, grant it
   (`GRANT TEMP ON DATABASE <db> TO <user>`).
5. Optional, but this is where the speed-up comes from: move field maps from faker callables to
   SQL expressions, for example:

   | before | after |
   |---|---|
   | `lambda f: f.email` | `seq_email()` |
   | `lambda f: lambda: f.ssn().replace("-", "")` | `seq_digits(9)` |
   | `lambda f: f.sentence` | `seq_text("Note")` |
   | `lambda f: f.first_name` | `fake_choice(lambda f: f.first_name)` (PostgreSQL) |
   | `json.loads` / `json.dumps` callable on a JSON text column | `jsonb_set_keys("col", key=value)` (PostgreSQL) |

   Callables that stay keep working. The Python path now loads only the callable columns.
6. For large tables on a remote database, consider `DEIDENTIFY_UPDATE_BATCH_SIZE = 50000` to keep
   transactions small (requires integer primary keys), and run `VACUUM ANALYZE` after the run.

## [0.1.0]

Initial release.
