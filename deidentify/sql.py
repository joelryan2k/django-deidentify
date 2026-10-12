import secrets
from collections.abc import Callable
from functools import cached_property

import faker
from django.db import NotSupportedError
from django.db.models import CharField, F, Func, TextField, Value
from django.db.models.functions import Cast, Concat, LPad

MAX_CONSECUTIVE_MISSES = 1000

TRY_JSONB_SQL ="""
CREATE OR REPLACE FUNCTION pg_temp.try_jsonb_object(t text) RETURNS jsonb AS $$
DECLARE v jsonb;
BEGIN
  v := t::jsonb;
  RETURN CASE WHEN jsonb_typeof(v) = 'object' THEN v END;
EXCEPTION WHEN others THEN RETURN NULL;
END $$ LANGUAGE plpgsql
"""


def ensure_functions(connection):
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(TRY_JSONB_SQL)


def _pk_text():
    return Cast(F("pk"), CharField())


def seq_text(prefix: str):
    return Concat(Value(f"{prefix} "), _pk_text(), output_field=CharField())


def seq_email(prefix: str = "user", domain: str = "example.com"):
    return Concat(Value(prefix), _pk_text(), Value(f"@{domain}"), output_field=CharField())


def seq_digits(width: int):
    return LPad(_pk_text(), width, Value("0"))


def _compile_all(compiler, expressions):
    sqls, params = [], []
    for expression in expressions:
        sql, p = compiler.compile(expression)
        sqls.append(sql)
        params.extend(p)
    return sqls, params


class FakeChoice(Func):
    output_field = TextField()

    def __init__(self, fake_fn: Callable[[faker.Faker], Callable], n: int, seed: int, locales):
        super().__init__(F("pk"))
        self.fake_fn, self.n, self.seed, self.locales = fake_fn, n, seed, locales
        self.salt = secrets.token_hex(4)

    @cached_property
    def pool(self) -> list[str]:
        fake = faker.Faker(self.locales)
        fake.seed_instance(self.seed)
        pool, misses = {}, 0
        while len(pool) < self.n and misses < MAX_CONSECUTIVE_MISSES:
            value = str(self.fake_fn(fake)())
            misses = misses + 1 if value in pool else 0
            pool[value] = None
        return list(pool)

    def as_sql(self, compiler, connection, **extra_context):
        raise NotSupportedError("fake_choice requires PostgreSQL")

    def as_postgresql(self, compiler, connection, **extra_context):
        (pk_sql,), params = _compile_all(compiler, self.get_source_expressions())
        return (
            f"(%s::text[])[1 + abs(mod(hashtext(({pk_sql})::text || %s), %s))]",
            [self.pool, *params, self.salt, len(self.pool)],
        )


def fake_choice(
    fake_fn: Callable[[faker.Faker], Callable],
    n: int = 5000,
    seed: int = 0,
    locales: str | list[str] | None = None,
):
    return FakeChoice(fake_fn, n, seed, locales)


class JsonbSetKeys(Func):
    output_field = TextField()

    def __init__(self, column: str, **values):
        expressions = [F(column)]
        for key, value in values.items():
            expressions.append(Value(key))
            expressions.append(value if hasattr(value, "resolve_expression") else Value(value))
        super().__init__(*expressions)

    def as_sql(self, compiler, connection, **extra_context):
        raise NotSupportedError("jsonb_set_keys requires PostgreSQL")

    def as_postgresql(self, compiler, connection, **extra_context):
        (column, *pairs), params = _compile_all(compiler, self.get_source_expressions())
        pairs_sql = ", ".join(f"({sql})::text" for sql in pairs)
        return (
            f"COALESCE((pg_temp.try_jsonb_object({column}) || jsonb_build_object({pairs_sql}))::text, '{{}}')",
            params,
        )


def jsonb_set_keys(column: str, **values):
    return JsonbSetKeys(column, **values)
