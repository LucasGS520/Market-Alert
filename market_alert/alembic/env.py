"""
Ambiente de execução do Alembic — configuração das migrations.

Este arquivo é carregado pelo Alembic ao rodar qualquer comando de migration
(upgrade, downgrade, revision, etc.). Ele:

    1. Importa todos os modelos para que o Alembic os detecte
    2. Resolve a URL de conexão com o banco (prioriza URL síncrona)
    3. Configura o modo online (conectado) ou offline (apenas SQL)

Por que URL síncrona para migrations?
    O Alembic CLI é síncrono (não usa asyncio). Por isso usamos
    psycopg2 em vez de asyncpg para rodar as migrations.

Como rodar:
    # Dentro do container da API ou localmente com env configurado:
    alembic upgrade head           → aplica todas as migrations pendentes
    alembic downgrade -1           → reverte a última migration
    alembic revision --autogenerate -m "descricao"  → cria nova migration
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importa todos os modelos para que o Alembic os detecte ao gerar migrations
import app.models  # noqa: F401
from app.core.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# O metadata com todas as tabelas definidas nos modelos
target_metadata = Base.metadata

# Resolve URL do banco: preferência pela URL síncrona (psycopg2)
# Se apenas DATABASE_URL estiver disponível, converte de asyncpg para psycopg2
_url_banco = (
    os.environ.get("DATABASE_SYNC_URL")
    or os.environ.get("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql+psycopg2://")
)
if _url_banco:
    config.set_main_option("sqlalchemy.url", _url_banco)


def run_migrations_offline() -> None:
    """
    Modo offline: gera o SQL das migrations sem conectar no banco.
    Útil para revisar as queries antes de aplicar em produção.
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
    """
    Modo online: conecta no banco e executa as migrations diretamente.
    É o modo padrão ao rodar `alembic upgrade head`.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # sem pool: conecta, migra e desconecta
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
