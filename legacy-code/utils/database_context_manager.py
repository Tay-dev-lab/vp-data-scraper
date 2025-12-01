from contextlib import contextmanager
from .database_config import Session

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()

@contextmanager
def read_only_session_scope():
    """Provide a read-only session scope."""
    session = Session()
    session.execute("SET TRANSACTION READ ONLY")
    try:
        yield session
        session.rollback()  # Always rollback, we're just reading
    finally:
        session.close()