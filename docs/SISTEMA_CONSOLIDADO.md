# Sistema Consolidado — Market Alert

> Branch analisada: `restructure-scraper`  
> Escopo: definição de responsabilidades, regras de negócio, fluxo operacional e contrato entre `market_alert` e `market_scraper`.  
> Objetivo principal: monitorar URLs diretas de marketplaces, coletar preço/disponibilidade de forma moderada em ambiente Docker local e acionar comparações/alertas sem usar proxies, APIs públicas de terceiros ou provedores externos de scraping.

---

## 1. Tese arquitetural

O sistema deve ser dividido em dois blocos com responsabilidades rígidas:

- `market_alert`: sistema de negócio. Decide quando coletar, o que fazer com sucesso/falha, quando retentar, quando pausar, quando comparar e quando notificar.
- `market_scraper`: serviço técnico de coleta e extração. Recebe uma URL direta de produto, tenta coletar dados brutos, extrai campos estruturados e devolve um resultado ou erro semântico.

O ponto crítico é não transformar o `market_scraper` em um scheduler, nem em um sistema de decisão. Ele deve continuar stateless e previsível. A política de frequência, rechecagem, retentativa e moderação contra bloqueio pertence ao `market_alert`.

---

## 2. Objetivo funcional

O sistema monitora produtos cadastrados por URL direta e, opcionalmente, concorrentes associados. Para cada URL, o sistema deve:

1. Coletar preço atual, título, disponibilidade, vendedor e metadados mínimos quando disponíveis.
2. Persistir histórico de preço.
3. Atualizar o estado atual do produto ou concorrente.
4. Comparar o produto principal com concorrentes cadastrados.
5. Emitir alertas apenas quando houver evento relevante.
6. Ajustar a próxima coleta com base na estabilidade ou mudança de preço.

Não é objetivo do sistema:

- Escalar scraping em alto volume.
- Usar rotação de IP, proxy residencial, APIs públicas de marketplace ou SaaS de scraping.
- Fazer crawling de categorias, busca ou descoberta de produtos.
- Coletar páginas fora de URLs diretas de produto.
- Expor o `market_scraper` como API pública para consumidores externos.

---

## 3. Componentes e responsabilidades

### 3.1 `market_alert_api`

Responsabilidades:

- Expor endpoints de cadastro, leitura e controle dos produtos monitorados.
- Validar entrada de usuário em nível de negócio.
- Persistir produtos, concorrentes, histórico, comparações e logs de notificação.
- Enfileirar coletas sob demanda quando aplicável.

Não deve:

- Executar scraping diretamente.
- Conhecer seletores CSS, APIs internas de marketplace ou detalhes de Playwright.
- Decidir parsing de HTML ou JSON de marketplace.

### 3.2 `market_alert_worker`

Responsabilidades:

- Executar tarefas Celery de coleta, comparação e notificação.
- Chamar `market_scraper` por meio de `ScraperClient`.
- Aplicar locks, rate limits, retries e transições de estado.
- Persistir os efeitos de negócio da coleta.

Não deve:

- Interpretar HTML.
- Corrigir preço recebido do scraper por heurísticas locais.
- Reimplementar lógica específica de marketplace.

### 3.3 `market_alert_beat`

Responsabilidades:

- Rodar o scheduler periódico.
- Identificar produtos ativos com `next_check_at <= agora`.
- Enfileirar tarefas de coleta.

Não deve:

- Chamar scraper diretamente.
- Fazer coleta síncrona.
- Alterar estado de produto exceto por enfileiramento indireto.

### 3.4 `market_scraper`

Responsabilidades:

- Expor endpoint interno `POST /scraper/parse`.
- Detectar o marketplace pela URL.
- Limpar parâmetros de rastreamento que não alteram o produto.
- Coletar HTML e payloads de rede por HTTP direto, Playwright ou estratégia híbrida.
- Detectar bloqueio, CAPTCHA, timeout e ausência de preço.
- Extrair dados estruturados com `confidence` e `extraction_method`.
- Retornar `ScrapeResult` em sucesso ou `ScrapeError` em falha semântica.

Não deve:

- Agendar coletas.
- Persistir histórico.
- Decidir próxima coleta.
- Enviar alerta.
- Retentar indefinidamente.
- Saber se uma URL é produto principal ou concorrente.
- Conhecer metas comerciais, limiares de alerta ou comparação competitiva.

Retries técnicos dentro de uma única tentativa, como tratar um HTTP 429 com `Retry-After`, são aceitáveis no scraper. Retry de negócio, retentativa futura e cooldown pertencem ao `market_alert`.

### 3.5 PostgreSQL

Responsabilidades:

- Fonte de verdade de produtos, concorrentes, histórico de preço, comparações e notificações.
- Armazenar o estado atual de monitoramento: `status`, `current_price`, `is_available`, `last_checked_at`, `next_check_at`, `check_interval_minutes`, `consecutive_unchanged`.

### 3.6 Redis

Responsabilidades:

- Broker/result backend do Celery.
- Locks de coleta.
- Rate limit por domínio/marketplace.
- Cooldown de notificações.
- Cache invalidável de comparação.

Redis não deve ser fonte de verdade para preço ou agenda.

---

## 4. Contrato entre `market_alert` e `market_scraper`

### 4.1 Requisição

```http
POST /scraper/parse
Content-Type: application/json
```

```json
{
  "url": "https://www.marketplace.com.br/produto-direto"
}
```

### 4.2 Sucesso

Campos esperados:

```json
{
  "marketplace": "magalu|mercadolivre|shopee",
  "url": "url limpa usada na coleta",
  "canonical_url": "url canônica quando disponível",
  "title": "nome do produto quando disponível",
  "price": "decimal positivo",
  "currency": "BRL",
  "available": true,
  "seller": "vendedor quando disponível",
  "product_id": "id externo quando disponível",
  "extraction_method": "network_payload|ssr_state|hydration_json|css_selector",
  "confidence": 0.0,
  "collected_at": "timestamp UTC"
}
```

Regras:

- `price` deve ser Decimal positivo.
- `currency` deve ser `BRL` enquanto o sistema operar apenas em marketplaces brasileiros.
- `confidence` deve representar qualidade técnica da extração, não decisão de negócio.
- `extraction_method` deve ser preservado pelo `market_alert` para diagnóstico e auditoria.

### 4.3 Falha semântica

Em falha de extração, o scraper deve retornar erro estruturado com:

```json
{
  "error_code": "PRICE_NOT_FOUND|CAPTCHA_DETECTED|BLOCKED|UNAVAILABLE|REDIRECT|LAYOUT_CHANGED|TIMEOUT|MARKETPLACE_NOT_SUPPORTED",
  "marketplace": "marketplace ou unknown",
  "url": "url processada",
  "retryable": true,
  "message": "descrição curta"
}
```

Regra obrigatória: o `market_alert` não deve descartar `error_code` nem `retryable`. Esses campos são a base para retry, cooldown, status e investigação.

---

## 5. Fluxo operacional ideal

### 5.1 Coleta programada de produto principal

1. `market_alert_beat` roda a cada minuto.
2. `scheduler_task` busca produtos com `status='active'` e `next_check_at <= agora`.
3. Para cada produto elegível, enfileira `collector_task(product_id=...)`.
4. `collector_task` abre sessão de banco, Redis e `ScraperClient`.
5. `collect_product` tenta adquirir lock `lock:collect:{product_id}`.
6. Se o lock já existir, a coleta é ignorada sem erro.
7. O serviço verifica rate limit por domínio/marketplace.
8. Se estiver em cooldown, a coleta é pulada e deve ser reavaliada no próximo ciclo.
9. `ScraperClient` chama `market_scraper`.
10. Em sucesso, o sistema:
    - grava `PriceHistory`;
    - atualiza `current_price`, `is_available`, `last_checked_at` e `status`;
    - preenche `name` se ainda estiver vazio e o scraper retornou título;
    - atualiza `consecutive_unchanged`;
    - recalcula `check_interval_minutes` e `next_check_at`.
11. O worker enfileira coletas dos concorrentes vinculados.
12. O worker enfileira `comparison_task`.
13. `comparison_task` recalcula ranking, status competitivo e estatísticas.
14. `notifications.evaluate_and_send` decide se há evento notificável e respeita cooldown.

### 5.2 Coleta de concorrente

1. Concorrentes são coletados após a coleta do produto principal ou sob demanda.
2. O fluxo usa lock e rate limit como produto principal.
3. Em sucesso, grava histórico e atualiza preço/disponibilidade do concorrente.
4. Concorrente não recalcula intervalo adaptativo próprio, salvo se isso for introduzido explicitamente como regra de negócio futura.

---

## 6. Regras de negócio de frequência e rechecagem

### 6.1 Frequência base

- Intervalo inicial recomendado por produto: 60 minutos.
- Intervalo mínimo de negócio: 30 minutos para produto ativo comum.
- Intervalo máximo: 240 minutos.
- O scheduler pode rodar a cada 1 minuto, mas isso não significa coletar cada produto a cada minuto.

Observação: o código atual permite limite técnico mínimo de 15 minutos, mas quando há mudança de preço força pelo menos 30 minutos. Para o objetivo de evitar bloqueios em IP local, a regra de negócio efetiva deve tratar 30 minutos como mínimo padrão, salvo execução manual controlada.

### 6.2 Intervalo adaptativo

- Se o preço mudou: reduzir o intervalo, sem ficar abaixo do mínimo definido.
- Se o preço ficou igual por 3 ou mais coletas consecutivas: dobrar o intervalo até o teto.
- Se ainda há poucas coletas estáveis: manter intervalo.

### 6.3 Retry e cooldown por erro

| Erro do scraper | Retry futuro? | Ação no `market_alert` |
|---|---:|---|
| `CAPTCHA_DETECTED` | Sim | Aplicar cooldown maior para o domínio/marketplace antes de nova tentativa. |
| `BLOCKED` | Sim | Marcar falha técnica, reduzir pressão sobre o domínio e retentar depois. |
| `TIMEOUT` | Sim | Retentar com backoff moderado. |
| `PRICE_NOT_FOUND` | Sim, limitado | Retentar poucas vezes; se persistir, marcar como erro de extração/layout. |
| `LAYOUT_CHANGED` | Sim, limitado | Abrir investigação no adapter; não insistir em alta frequência. |
| `UNAVAILABLE` | Não por retry imediato | Persistir indisponibilidade e seguir próxima coleta normal. |
| `REDIRECT` | Não | Marcar URL inválida ou produto não direto. |
| `MARKETPLACE_NOT_SUPPORTED` | Não | Rejeitar cadastro ou marcar URL sem suporte. |

Regra: retry automático do Celery não deve ser aplicado cegamente a todo 422. Ele deve respeitar `retryable`.

### 6.4 Rate limit

Rate limit mínimo deve existir em duas camadas:

1. Por item monitorado: via `next_check_at`.
2. Por domínio/marketplace: via Redis.

O TTL atual por domínio é curto e funciona como proteção contra rajadas simultâneas, não como política completa anti-bloqueio. Para operação local sem proxy, a política de negócio deve priorizar baixa concorrência e cadência moderada.

Regras práticas:

- Evitar múltiplas coletas simultâneas no mesmo domínio.
- Preferir fila de coleta com baixa concorrência.
- Concorrentes do mesmo marketplace devem respeitar cooldown compartilhado por domínio.
- CAPTCHA ou 403 deve aumentar temporariamente o cooldown.
- Recoletas manuais devem passar pelas mesmas proteções de lock/rate limit, salvo modo diagnóstico explícito.

---

## 7. Regras para o `market_scraper`

### 7.1 Entrada

- Receber apenas URL direta.
- Validar domínio suportado.
- Limpar parâmetros de rastreamento antes de navegar ou fazer HTTP.

### 7.2 Coleta

- Escolher estratégia por marketplace:
  - Magalu: HTTP SSR primeiro, browser como fallback.
  - Shopee: browser e payloads de rede como fonte preferencial.
  - Mercado Livre: browser com suporte a layouts diferentes.
- Capturar payloads relevantes sem bloquear navegação.
- Detectar CAPTCHA e bloqueio.
- Persistir sessão/cookies por marketplace quando rodar em Docker.

### 7.3 Extração

- Extrair em ordem de confiabilidade:
  1. payload de rede;
  2. estado SSR/hydration;
  3. JSON estruturado quando aplicável;
  4. seletores CSS como fallback.
- Retornar `confidence` coerente.
- Não classificar impacto comercial.
- Não decidir se uma variação de preço merece alerta.

### 7.4 Saída

- Nunca retornar preço inválido como sucesso.
- Nunca esconder CAPTCHA, 403 ou timeout como `PRICE_NOT_FOUND` genérico quando houver sinal claro.
- Sempre devolver erro semântico com `retryable` quando a falha for conhecida.

---

## 8. Pontos fracos identificados na branch atual

### 8.1 Perda do contrato de erro no `ScraperClient`

O scraper retorna erro com `error_code` e `retryable`, mas o cliente do `market_alert` transforma o 422 em exceção genérica. Isso impede o negócio de distinguir erro retryable de erro definitivo.

Correção recomendada:

- Criar modelo `ScraperErrorResult` no `market_alert`.
- Fazer `ScraperParseError` carregar `error_code`, `retryable`, `marketplace` e `message`.
- No `collector_task`, aplicar `self.retry()` apenas se `retryable=True`.

### 8.2 `ScraperResult` do `market_alert` perde metadados úteis

O resultado local preserva preço, disponibilidade, título, seller, currency e `collected_at`, mas não preserva campos como `url`, `canonical_url`, `product_id`, `extraction_method` e `confidence`.

Correção recomendada:

- Expandir o schema do `market_alert` para refletir o contrato completo do scraper.
- Persistir pelo menos `extraction_method` e `confidence` no histórico ou em logs estruturados.

### 8.3 Concorrência de coleta pode ser alta para IP único

O Docker define worker de coleta com concorrência 4. Para uso local sem proxy e com browser compartilhado, isso pode gerar rajadas no mesmo domínio se vários produtos vencerem `next_check_at` juntos.

Correção recomendada:

- Reduzir a concorrência da fila `collection` ou separar worker de coleta com `--concurrency=1` ou `2`.
- Manter comparação em fila separada com concorrência maior, pois não faz scraping.
- Tornar cooldown por marketplace configurável.

### 8.4 Rate limit por domínio é técnico, não regra completa

O TTL de 5 segundos evita duplicidade imediata, mas não é suficiente como política anti-bloqueio. A proteção real deve combinar `next_check_at`, baixa concorrência, backoff por erro e cooldown por domínio.

### 8.5 Arquivo `.env` rastreado no repositório

Existe um `.env` no repositório. Se contiver credenciais reais, tokens ou URLs sensíveis, deve ser removido do controle de versão e substituído por `.env.example`.

---

## 9. Ordem recomendada de implementação

### Fase 1 — Contrato e fronteira

1. Ajustar `ScraperClient` para preservar erro estruturado.
2. Expandir `ScraperResult` no `market_alert`.
3. Definir mapeamento de erro para status/retry/cooldown.
4. Garantir que `market_scraper` continue sem regra de negócio.

### Fase 2 — Operação moderada em Docker

1. Reduzir concorrência da fila de coleta.
2. Tornar cooldown por domínio/marketplace configurável.
3. Persistir `.session_state` do scraper como volume Docker.
4. Adicionar logs de diagnóstico por tentativa: marketplace, método, confidence, status_code, retryable.

### Fase 3 — Correções específicas do `market_scraper`

1. Testar adapters com URLs reais salvas por marketplace.
2. Corrigir seletores/payloads por marketplace.
3. Criar testes unitários de extração com HTML/payload fixtures.
4. Só depois ajustar estratégias Playwright/HTTP.

### Fase 4 — Regras comerciais adicionais

1. Refinar comparação competitiva.
2. Refinar notificações.
3. Adicionar política de pausa automática após falhas consecutivas, se necessário.

---

## 10. Critérios de aceite

O sistema estará alinhado quando:

- `market_scraper` puder ser testado isoladamente com uma URL e retornar sucesso/erro sem depender do banco.
- `market_alert` controlar toda decisão de agenda, retry, cooldown e persistência.
- Erros do scraper não forem reduzidos a exceções genéricas.
- A frequência de coleta for controlada por regra de negócio e não por loop interno no scraper.
- O Docker subir todos os serviços localmente sem depender de proxy ou scraping SaaS.
- Cada coleta deixar rastro auditável: produto, marketplace, preço, disponibilidade, método de extração, confidence, erro quando houver.
- CAPTCHA/403 reduzirem a pressão sobre o domínio em vez de acelerar retentativas.

---

## 11. Decisão final de desenho

Antes de corrigir problemas operacionais no `market_scraper`, a prioridade deve ser consolidar o contrato entre os serviços. O maior risco atual não é apenas um seletor quebrado ou um wait incorreto no Playwright; é o `market_alert` não usar corretamente os sinais que o scraper já emite.

A correção do scraper deve vir depois da fronteira estar estável. Caso contrário, cada ajuste técnico pode virar regra implícita e dificultar a manutenção do sistema.
