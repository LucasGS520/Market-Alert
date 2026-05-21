"""price_history: alterar FK constraints de SET NULL para CASCADE

Revision ID: 011
Revises: 010
Create Date: 2026-05-13 00:00:00.000000

Problema:
    Os FKs monitored_id e competitor_id em price_history usavam ON DELETE SET NULL,
    mas o check constraint ck_price_history_single_owner exige que exatamente um dos
    dois seja NOT NULL. Ao deletar um produto monitorado, o banco tentava setar
    monitored_id=NULL em linhas sem competitor_id, violando o constraint.

Correcao:
    Altera ambos os FKs para ON DELETE CASCADE. Ao deletar um produto ou concorrente,
    todas as linhas de price_history associadas sao removidas junto.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_monitored_id_fkey")
    op.execute("""
        ALTER TABLE price_history
        ADD CONSTRAINT price_history_monitored_id_fkey
        FOREIGN KEY (monitored_id) REFERENCES monitored_products(id) ON DELETE CASCADE
    """)
    op.execute("ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_competitor_id_fkey")
    op.execute("""
        ALTER TABLE price_history
        ADD CONSTRAINT price_history_competitor_id_fkey
        FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE CASCADE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_monitored_id_fkey")
    op.execute("""
        ALTER TABLE price_history
        ADD CONSTRAINT price_history_monitored_id_fkey
        FOREIGN KEY (monitored_id) REFERENCES monitored_products(id) ON DELETE SET NULL
    """)
    op.execute("ALTER TABLE price_history DROP CONSTRAINT IF EXISTS price_history_competitor_id_fkey")
    op.execute("""
        ALTER TABLE price_history
        ADD CONSTRAINT price_history_competitor_id_fkey
        FOREIGN KEY (competitor_id) REFERENCES competitors(id) ON DELETE SET NULL
    """)
