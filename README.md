# Tradebot Bitcoin

Robô especialista em **BTCUSDT Spot na Binance**, baseado em regime de mercado, momentum ajustado por volatilidade, tendência, risco e execução segura.

> Projeto educacional e experimental. Não é recomendação financeira. Use primeiro em paper trade.

## Estratégia confirmada

Nome: **Vini BTC Regime Momentum Bot v1**

O bot não tenta prever cada candle. Ele identifica o regime do Bitcoin:

1. Bear/defesa: fica em USDT.
2. Reversão/acumulação: compra pequeno.
3. Alta confirmada: aumenta exposição.
4. Alta madura/distribuição: reduz posição.
5. Euforia/topo: vende parcial ou sai.

### Coração da lógica

```text
Macro favorável + preço acima da tendência + momentum positivo + volatilidade aceitável = compra/tendência.

Macro piorando + perda da SMA200D + momentum negativo = defesa/venda.

Alta esticada + divergência + volume vendedor = venda parcial/proteção.
```

## Ativo

- Mercado: Spot
- Par: BTCUSDT
- Exchange: Binance
- Frequência de decisão: 15 minutos
- Sinais principais: candles fechados de 1d, 4h e 1h

## Arquivos importantes

```text
bot.py                     Entrada principal
config.example.yaml         Modelo de configuração sem segredos
.env.example                Modelo das variáveis de ambiente
tradebot/                   Código principal
```

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
```

Edite `.env` com suas chaves da Binance e `config.yaml` com o modo desejado.

## Rodar em paper trade

```bash
python bot.py --config config.yaml
```

## Segurança

Nunca suba estes arquivos para o GitHub:

```text
.env
config.yaml
logs/
state.json
positions.json
*.db
*.jsonl
```

## Regras de risco padrão

- Exposição máxima: 60%
- Caixa mínimo: 40%
- Risco por trade: 0,75%
- Stop padrão: ATR ou 8–12%
- Trailing stop: 8–15%, conforme volatilidade
- Pausa após perdas consecutivas

## Modos

```yaml
exchange:
  mode: paper  # paper ou trade
```

Comece com `paper`. Só use `trade` depois de logs limpos, backtest e paper trade consistente.
