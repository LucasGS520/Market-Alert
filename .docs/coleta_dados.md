Para esse sistema, o fluxo de coleta dos dados é crucial para o bom funcionamento desse sistema.
Isso significa que:
* cobertura importa mais que pureza arquitetural
* precisão do preço importa mais que “API oficial”
* disponibilidade contínua importa mais que legalismo idealizado
* você precisa de dados reais do marketplace, não de feeds externos incompletos

E isso leva a uma conclusão desconfortável:

Para Mercado Livre + Shopee + Magalu, você inevitavelmente precisará de algum nível de coleta baseada em frontend.

A questão deixa de ser:

> “Como evitar scraping?”

e passa a ser:

> “Como fazer coleta controlada, sustentável e de baixa manutenção?”

Essa é a decisão correta.

---

# Os dados e fonte necessários a serem coletados

* seus concorrentes estão dentro do marketplace
* o preço real competitivo está lá
* Buy Box está lá
* promoções estão lá
* sellers terceiros estão lá

Então o sistema precisa monitorar:

* o anúncio real
* dentro do marketplace real

---

# A arquitetura correta para seu cenário

Já temos a base correta no projeto atual. 

O sistema:
* já é orientado a URLs
* já possui workers
* já possui histórico
* já possui scheduler
* já possui locks/rate limits
* já possui scraper desacoplado

Ou seja:
- NÃO precisamos reinventar a arquitetura.
- Precisamos evoluir o `market_scraper`.

---

# O caminho ideal REALISTA

## NÃO tente:

* scraping distribuído enterprise
* crawling massivo
* indexação total do marketplace
* descoberta automática de catálogo

Isso explode manutenção.

---

# Faça isso:

## Sistema orientado a produtos monitorados

Fluxo:

```text
Produto monitorado Adicionado
    ↓
URLs concorrentes específicas
    ↓
Coleta controlada
    ↓
Histórico
    ↓
Alertas
```

Isso é totalmente viável.

---

# Melhor arquitetura agora

## 1. Substituir scraping HTML bruto

O `market_scraper` atual:
* baixa HTML
* parseia DOM

Isso é frágil.

---

# O que fazer no lugar

## Detectar APIs internas públicas do frontend

Todos esses marketplaces usam APIs internas consumidas pelo próprio frontend React/Vue.

Você NÃO quer:
* parsear HTML

Você quer:
* interceptar os JSONs internos

---

# Mercado Livre

O frontend consome APIs internas JSON.

Muitas páginas possuem:
* estado serializado
* payloads JSON
* APIs de item

O sistema deve conseguir:
* título
* preço
* seller
* shipping
* disponibilidade

sem parsear DOM inteiro.

---

# Shopee

A Shopee é a mais problemática.

Mas ainda assim:
* frontend consome APIs JSON
* mobile APIs existem
* GraphQL interno existe em algumas regiões

O problema:
* proteção anti-bot agressiva

---

# Magalu

Muito mais tranquilo que Shopee.

Vários dados:
* já vêm serializados
* endpoints internos são mais simples

---

# O que isso muda no seu sistema

Seu `market_scraper` deixa de ser:

```text
HTML parser
```

e vira:

```text
Marketplace adapters
```

---

# Cada adapter

Responsável por:
* detectar marketplace
* obter payload correto
* normalizar resposta

---

# Estrutura ideal

## Entrada

```json id="4zq8a3"
{
  "url": "https://produto..."
}
```

---

## Saída padronizada

```json id="6pvx7z"
{
  "marketplace": "mercadolivre",
  "title": "...",
  "price": 199.90,
  "seller": "...",
  "available": true,
  "currency": "BRL",
  "collected_at": "..."
}
```

---

# Isso é MUITO importante

Seu sistema principal NÃO deve conhecer:
* Shopee
* Mercado Livre
* Magalu

Só o `market_scraper`.

A API principal continua intacta. 

---

# Estratégia mais importante

## Pare de coletar por busca

NÃO faça:

```text
buscar "iphone"
listar marketplace inteiro
```

---

# Faça:

```text
monitorar URLs específicas
```

Porque:

* reduz bloqueio
* reduz tráfego
* reduz manutenção
* reduz risco

E seu sistema já foi desenhado exatamente assim. 

---

# O maior erro possível agora

Seria tentar:
* transformar isso em crawler de marketplace
* descoberta automática massiva
* indexador global

Isso destruiria:
* simplicidade operacional
* custo
* estabilidade

---

# O que evitar

Não use:

* Selenium contínuo
* Playwright para tudo
* browser automation em massa

Use browser automation apenas:
* como fallback extremo
* para reverse engineering
* ou páginas quebradas

---

# Decisão final correta para seu cenário

* coleta controlada por URL
* adapters especializados
* parsing de APIs internas do frontend
* scraping mínimo possível

Essa é a arquitetura correta para o seu caso real.
