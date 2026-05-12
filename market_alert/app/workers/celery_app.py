"""
Configuração do Celery — fila de tarefas assíncronas.

O Celery processa tarefas em background sem bloquear a API. Neste projeto,
três tipos de tarefas existem:

    collector_task  → coleta preço de um produto ou concorrente
    comparison_task → recalcula ranking e status competitivo
    scheduler_task  → roda a cada 1 minuto via Beat; decide quais produtos coletar

Filas separadas:
    collection → tarefas de coleta (podem ser lentas por I/O de rede)
    comparison → cálculos (rápidos, dependem apenas do banco)
    default    → scheduler e outras tarefas utilitárias

Por que Redis como broker?
    Já está na stack para locks e cache. Evita adicionar outro serviço
    (como RabbitMQ) para um projeto de escopo local.
"""

from celery import Celery
from celery.schedules import crontab

from app.infra.config import settings

celery_app = Celery("market_alert")

celery_app.conf.update(
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,

    # Serialização em JSON (legível e segura; evita pickle)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Confirma a tarefa como concluída APÓS processar (não antes)
    # Garante que tarefas não se percam se o worker morrer no meio
    task_acks_late=True,

    # Pega apenas 1 tarefa por vez por processo (evita acúmulo em memória)
    worker_prefetch_multiplier=1,

    # Roteamento: cada tipo de tarefa vai para a fila correspondente
    task_routes={
        "app.workers.tasks.collector_task": {"queue": "collection"},
        "app.workers.tasks.comparison_task": {"queue": "comparison"},
        "app.workers.tasks.notification_task": {"queue": "notification"},
        "app.workers.tasks.scheduler_task": {"queue": "default"},
    },

    # Agenda periódica do Beat: roda o scheduler a cada minuto
    beat_schedule={
        "verificar-produtos-a-coletar": {
            "task": "app.workers.tasks.scheduler_task",
            "schedule": crontab(minute="*"),  # equivale a "* * * * *" no cron
        }
    },

    timezone="UTC",
)

# Descobre automaticamente as tarefas no módulo app.workers.tasks
celery_app.autodiscover_tasks(["app.workers"])
