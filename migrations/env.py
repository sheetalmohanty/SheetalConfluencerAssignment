from alembic import context
from sqlalchemy import create_engine, pool

from app import models  # noqa: F401
from app.config import get_settings
from app.database import Base


def run_migrations():
    if context.is_offline_mode():
        context.configure(
            url=get_settings().database_url,
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
        )
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


run_migrations()
