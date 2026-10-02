from pathlib import Path
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from .config import S

pool = ConnectionPool(S.database_url, min_size=1, max_size=10, kwargs={"row_factory": dict_row}, open=False)


def init():
    pool.open()
    with pool.connection() as c:
        c.execute((Path(__file__).parent / "schema.sql").read_text())


def q(sql, args=(), one=False):
    """Run one statement in its own transaction. Returns a row (one=True) or a list."""
    with pool.connection() as c:
        cur = c.execute(sql, args)
        if cur.description is None:
            return None
        return cur.fetchone() if one else cur.fetchall()
