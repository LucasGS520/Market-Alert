"""
Configuração do banco de dados PostgreSQL via SQLAlchemy assíncrono.

Este módulo define:
- O engine assíncrono (usando asyncpg como driver)
- O factory de sessões (AsyncSessionLocal)
- A classe Base que todos os modelos ORM herdam

Por que assíncrono?
    A API FastAPI é ASGI e executa requisições concorrentemente. Usar
    SQLAlchemy assíncrono evita bloquear o event loop enquanto espera
    respostas do banco — essencial para performance.

Uso nos endpoints FastAPI:
    from app.core.database import get_session
    # Injetar como dependência no endpoint
    async def meu_endpoint(session: AsyncSession = Depends(get_session)):
        ...

Uso nos workers Celery:
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Engine assíncrono — gerencia o pool de conexões com o PostgreSQL
# pool_pre_ping=True: testa a conexão antes de usá-la (evita conexões mortas)
engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

# Factory de sessões — cada requisição/tarefa cria a sua própria sessão
# expire_on_commit=False: mantém os objetos acessíveis após o commit
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Classe base que todos os modelos SQLAlchemy devem herdar."""
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependência FastAPI que fornece uma sessão de banco de dados.

    Abre a sessão no início da requisição e a fecha automaticamente
    ao final, mesmo em caso de erro (context manager assíncrono).
    """
    async with AsyncSessionLocal() as session:
        yield session
