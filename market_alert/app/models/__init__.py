"""
Pacote models — modelos SQLAlchemy que mapeiam as tabelas do PostgreSQL.

Importar este pacote garante que todas as classes de modelo sejam
registradas no metadata do SQLAlchemy antes de qualquer operação,
o que é necessário tanto para o Alembic (autogenerate) quanto
para as relações entre modelos funcionarem corretamente.

Tabelas criadas:
    monitored_products → produtos sendo acompanhados
    competitors        → concorrentes de cada produto
    price_history      → histórico de coletas de preço
    comparisons        → análises competitivas calculadas
    notification_logs  → registro de alertas enviados
"""

from app.models.comparison import Comparison
from app.models.competitor import Competitor
from app.models.monitored_product import MonitoredProduct
from app.models.notification_log import NotificationLog
from app.models.price_history import PriceHistory

__all__ = [
    "MonitoredProduct",
    "Competitor",
    "PriceHistory",
    "Comparison",
    "NotificationLog",
]
