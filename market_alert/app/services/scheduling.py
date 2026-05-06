"""
Serviço de agendamento adaptativo de coletas.

Em vez de checar cada produto sempre no mesmo intervalo fixo, o sistema
ajusta dinamicamente a frequência com base na estabilidade do preço:

    - Preço mudou na última coleta   → próxima coleta mais cedo (intervalo cai pela metade)
    - Preço estável por 3+ coletas   → próxima coleta mais tarde (intervalo dobra)
    - Caso contrário                 → mantém o intervalo atual

Limites absolutos:
    Mínimo: 15 minutos  (não bombardeia o site alvo)
    Máximo: 240 minutos (garante atualização pelo menos a cada 4 horas)

Exemplo de comportamento:
    Intervalo inicial: 60 min
    Preço muda → 30 min
    Preço estável × 3 → 60 min → 120 min → 240 min (teto)
"""

# Limites de intervalo em minutos
_INTERVALO_MINIMO = 15
_INTERVALO_MAXIMO = 240


def compute_next_interval(
    current_interval: int,
    price_changed: bool,
    consecutive_unchanged: int,
) -> int:
    """
    Calcula o próximo intervalo de coleta em minutos.

    Args:
        current_interval:     Intervalo atual em minutos.
        price_changed:        True se o preço mudou na última coleta.
        consecutive_unchanged: Quantas coletas consecutivas o preço ficou igual.

    Returns:
        Novo intervalo em minutos, sempre entre 15 e 240.
    """
    if price_changed:
        # Preço instável: acelerar a frequência (mínimo de 30 min para não sobrecarregar)
        intervalo_reduzido = max(_INTERVALO_MINIMO, current_interval // 2)
        return max(intervalo_reduzido, 30)

    if consecutive_unchanged >= 3:
        # Preço muito estável: economizar recursos dobrando o intervalo
        return min(_INTERVALO_MAXIMO, current_interval * 2)

    # Sem mudanças mas ainda dentro das primeiras coletas estáveis: mantém
    return current_interval
