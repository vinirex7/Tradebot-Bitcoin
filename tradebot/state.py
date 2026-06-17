import json
from pathlib import Path
from typing import Any


DEFAULT_STATE = {
    "paper_equity_usdt": 1000.0,
    "position": {
        "in_position": False,
        "entry_price": 0.0,
        "position_qty": 0.0,
        "position_usdt": 0.0,
        "peak_price": 0.0,
        "stop_price": 0.0,
        "take_profit_1_done": False,
        "take_profit_2_done": False,
        "entry_reason": "",
    },
}


def load_state(path: str) -> dict[str, Any]:
    file = Path(path)
    if not file.exists():
        return json.loads(json.dumps(DEFAULT_STATE))
    with file.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict[str, Any]) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True) if file.parent != Path('.') else None
    with file.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def append_jsonl(path: str, row: dict[str, Any]) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
