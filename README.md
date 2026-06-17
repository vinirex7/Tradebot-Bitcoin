# Tradebot Bitcoin

Robô especialista em **BTCUSDT Spot na Binance**, com duas linhas de estratégia:

1. **Vini BTC Regime Momentum Bot v3**: modelo antigo de entrada/saída por sinal.
2. **BTC Modern Regime Allocation v1**: modelo novo de alocação dinâmica por regime, pensado para o Bitcoin dos últimos anos.

> Projeto educacional e experimental. Não é recomendação financeira. Use primeiro em backtest e paper trade.

## Estratégia nova: BTC Modern Regime Allocation v1

A estratégia nova não tenta apenas decidir `BUY` ou `SELL`. Ela calcula uma **alocação alvo em BTC**.

| Regime | Alvo em BTC |
|---|---:|
| Bear forte | 0% |
| Bear enfraquecendo | 20% |
| Neutro estrutural | 20% |
| Acumulação/recuperação | 35% |
| Alta confirmada | 70% |
| Alta forte | 85% |
| Euforia esfriando | 60% |

A ideia é evitar o erro dos backtests antigos: ficar tempo demais em USDT e perder grandes movimentos do Bitcoin.

## Arquivos importantes

```text
bot.py                         Bot antigo por sinais
backtest.py                    Backtest antigo por sinais
bot_allocation.py              Bot novo por alocação
backtest_allocation.py         Backtest novo por alocação
config.example.yaml            Config exemplo do bot antigo
config_allocation.example.yaml Config exemplo do bot novo
backtest.example.yaml          Config exemplo do backtest antigo
backtest_allocation.yaml       Config do backtest novo
tradebot/                      Código principal
```

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Rodar backtest da estratégia nova

O backtest usa dados públicos da Binance e não envia ordens.

```bash
python backtest_allocation.py --config backtest_allocation.yaml --save
cat backtests/allocation_results/metrics.json
```

Saídas geradas em `backtests/allocation_results/`:

```text
metrics.json       Métricas principais
equity_curve.csv   Curva de patrimônio
trades.csv         Rebalanceamentos simulados
decisions.csv      Decisões diárias do modelo
```

Métricas calculadas:

```text
retorno total
CAGR
max drawdown
Sharpe
Sortino
exposure time
alocação média em BTC
resultado vs buy and hold
```

## Rodar bot novo em paper trade

```bash
cp config_allocation.example.yaml config_allocation.yaml
python bot_allocation.py --config config_allocation.yaml --once
```

Para rodar continuamente:

```bash
python bot_allocation.py --config config_allocation.yaml
```

## Rodar backtest antigo

```bash
cp backtest.example.yaml backtest.yaml
python backtest.py --config backtest.yaml --save
cat backtests/results/metrics.json
```

## Segurança

Nunca suba estes arquivos para o GitHub:

```text
.env
config.yaml
config_allocation.yaml
backtest.yaml
logs/
state.json
allocation_state.json
positions.json
*.db
*.jsonl
backtests/results/
backtests/allocation_results/
```

## Modos

```yaml
exchange:
  mode: paper  # paper ou trade
```

Comece com `paper`. Só use `trade` depois de logs limpos, backtest e paper trade consistente.
