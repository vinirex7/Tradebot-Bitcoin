# Tradebot Bitcoin

Robô especialista em **BTCUSDT Spot na Binance**, com duas linhas de estratégia:

1. **Vini BTC Regime Momentum Bot v3**: modelo antigo de entrada/saída por sinal.
2. **BTC Modern Regime Allocation v2 Improved**: modelo atual de alocação dinâmica por regime, pensado para o Bitcoin dos últimos anos.

> Projeto educacional e experimental. Não é recomendação financeira. Use primeiro em backtest e paper trade.

## Estratégia atual: BTC Modern Regime Allocation v2 Improved

A estratégia atual não tenta apenas decidir `BUY` ou `SELL`. Ela calcula uma **alocação alvo em BTC** conforme o regime de mercado.

| Regime | Alvo em BTC |
|---|---:|
| Bear forte | 0% |
| Bear enfraquecendo | 20% |
| Chop/lateralização | 20% |
| Neutro estrutural | 25% |
| Acumulação/recuperação | 45% |
| Alta confirmada | 80% |
| Alta forte | 95% |
| Euforia esfriando | 70% |

A versão v2 Improved também usa:

- filtro de lateralização/chop;
- redução de alocação em volatilidade alta;
- alocação máxima de 95%;
- rebalanceamento apenas quando a diferença para o alvo for de pelo menos 15%.

A ideia é evitar o erro dos backtests antigos: ficar tempo demais em USDT e perder grandes movimentos do Bitcoin.

## Arquivos importantes

```text
bot.py                              Bot antigo por sinais
backtest.py                         Backtest antigo por sinais
bot_allocation.py                   Bot atual por alocação
backtest_allocation.py              Backtest atual por alocação
config.example.yaml                 Config exemplo do bot antigo
config_allocation.example.yaml      Config live/paper alinhada ao backtest v2 Improved
backtest.example.yaml               Config exemplo do backtest antigo
backtest_allocation_v2_improved.yaml Config do backtest atualizado
tradebot/                           Código principal
```

## Instalação

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Rodar backtest da estratégia atual

O backtest usa dados públicos da Binance e não envia ordens.

```bash
python backtest_allocation.py --config backtest_allocation_v2_improved.yaml --save
cat backtests/allocation_results_v2_improved/metrics.json
```

Saídas geradas em `backtests/allocation_results_v2_improved/`:

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

## Rodar bot atual em paper trade

```bash
cp config_allocation.example.yaml config_allocation.yaml
python bot_allocation.py --config config_allocation.yaml --once
```

Para rodar continuamente:

```bash
python bot_allocation.py --config config_allocation.yaml
```

## Rodar em screen na VPS

```bash
screen -S allocation-live
python bot_allocation.py --config config_allocation.yaml
```

Para sair sem parar o bot:

```text
Ctrl + A
D
```

Para voltar:

```bash
screen -r allocation-live
```

Para ver as últimas decisões:

```bash
tail -20 logs/allocation_decisions.jsonl
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
backtests/allocation_results_v2_improved/
```

## Modos

```yaml
exchange:
  mode: paper  # paper ou trade
```

Comece com `paper`. Só use `trade` depois de logs limpos, backtest e paper trade consistente.
