from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from sports_passport.core.config import settings

# Importing the models is what populates Base.metadata, which is what
# --autogenerate diffs the database against. They are never referenced by
# name here, but dropping them would make autogenerate emit a migration
# that deletes every table.
from sports_passport.db.database import Base
from sports_passport.models import (  # noqa: F401
    Game,
    League,
    Team,
    User,
    UserGameAttendance,
    Venue,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Migrate the same database the app uses (DATABASE_URL / .env), not the
# hardcoded ini fallback — in Docker the app DB lives on the /app/data volume.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
