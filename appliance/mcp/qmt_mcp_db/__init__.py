"""Optional PostgreSQL persistence (feature 012).

Off by default; enabled by QMT_DB_URL. Native-async (asyncpg) behind a sync facade
so the existing sync tool/worker model is unchanged. First domain: market-data
warehouse (bars/history). Pure-logic modules (dsn/coverage/rows) import without
asyncpg; only `engine` touches the driver (lazily).
"""
