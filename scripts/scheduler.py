# -*- coding: utf-8 -*-
"""间隔复习调度器：FSRS 核心算法的项目化实现。

算法来源：开源 FSRS（open-spaced-repetition/fsrs-rs，v4.5 风格核心公式）：
- 遗忘曲线 R(t, S) = (1 + FACTOR * t / S) ** DECAY，FACTOR = 19/81，DECAY = -0.5
- 初始稳定性 S0 = w[grade-1]（前 4 个默认参数）
- 初始难度 D0 = w[4] - exp(w[5] * (grade-1)) + 1
- 复习后难度带线性阻尼与均值回归：D' = D0(g) * 0.01 + D_new * 0.99（mean reversion）
- 下一间隔由期望保持率反解遗忘曲线：t = S / FACTOR * (dr ** (1/DECAY) - 1)

与本项目错题队列（ReviewQueue 1.1）的集成：
- 条目若带 `fsrs` 字段 {"s": 稳定性, "d": 难度} 则直接使用（精确状态）；
- 否则按 status 做启发式 bootstrap（mastered→S=21 / due→S=7 / pending→S=4 / retesting→S=2），
  此映射为文档化启发式，不是 FSRS 推断结果；条目被评级后建议写回 `fsrs` 字段以进入精确态。

CLI：
    python scripts/scheduler.py --queue demo-vault/30-知识/错题队列.json [--today 2026-09-14]
输出 JSON：每条含 suggested_next_date / retrievability_today / bootstrapped 标记。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

# FSRS-4.5 默认参数（17 维），来源 fsrs-rs DEFAULT 参数集
W = [0.4, 0.6, 2.4, 5.8, 4.93, 0.94, 0.86, 0.01, 1.49, 0.14, 0.94,
     2.18, 0.05, 0.34, 1.26, 0.29, 2.61]
FACTOR = 19.0 / 81.0
DECAY = -0.5
DESIRED_RETENTION = 0.9
D_MIN, D_MAX = 1.0, 10.0
INTERVAL_MIN, INTERVAL_MAX = 1, 365

GRADES = {"again": 1, "hard": 2, "good": 3, "easy": 4}
STATUS_BOOTSTRAP = {"mastered": 21.0, "due": 7.0, "pending": 4.0, "retesting": 2.0}


def retrievability(t_days: float, stability: float) -> float:
    """FSRS 遗忘曲线：t 天后的可提取概率。"""
    s = max(stability, 0.1)
    return (1.0 + FACTOR * max(t_days, 0.0) / s) ** DECAY


def next_interval(stability: float, desired_retention: float = DESIRED_RETENTION) -> int:
    """由期望保持率反解下一复习间隔（天）。"""
    raw = stability / FACTOR * (desired_retention ** (1.0 / DECAY) - 1.0)
    return int(min(max(round(raw), INTERVAL_MIN), INTERVAL_MAX))


def init_state(grade: str) -> tuple[float, float]:
    g = GRADES[grade]
    s = W[g - 1]
    d = W[4] - math.exp(W[5] * (g - 1)) + 1.0
    return s, min(max(d, D_MIN), D_MAX)


def _linear_damping(delta_d: float, old_d: float) -> float:
    return (10.0 - old_d) * delta_d / 9.0


def _mean_reversion(init_d: float, current_d: float) -> float:
    return init_d * 0.01 + current_d * 0.99


def review(s: float, d: float, elapsed_days: float, grade: str) -> tuple[float, float]:
    """复习一次后的 (新稳定性, 新难度)。again=遗忘重学，其余=成功回忆。"""
    r = retrievability(elapsed_days, s)
    g = GRADES[grade]
    d0 = W[4] - math.exp(W[5] * (g - 1)) + 1.0
    if grade == "again":
        new_s = W[11] * (d ** -W[12]) * (((s + 1.0) ** W[13]) - 1.0) * math.exp(W[14] * (1.0 - r))
        new_s = max(min(new_s, s), 0.1)  # 失败不应提升稳定性
    else:
        hard_easy = W[15] if grade == "hard" else (W[16] if grade == "easy" else 1.0)
        new_s = s * (1.0 + math.exp(W[8]) * (11.0 - d) * (s ** -W[9])
                     * (math.exp(W[10] * (1.0 - r)) - 1.0) * hard_easy)
        new_s = max(new_s, 0.1)
    delta_d = -W[6] * (g - 3)
    d_after = d + _linear_damping(delta_d, d)
    new_d = min(max(_mean_reversion(d0, d_after), D_MIN), D_MAX)
    return new_s, new_d


def schedule_item(item: dict, today: date) -> dict:
    """为队列条目计算建议复习日；无 fsrs 精确状态时按 status 启发式 bootstrap。"""
    fsrs = item.get("fsrs")
    bootstrapped = not (isinstance(fsrs, dict) and "s" in fsrs and "d" in fsrs)
    if bootstrapped:
        s = STATUS_BOOTSTRAP.get(item.get("status"), 4.0)
        d = 5.0
    else:
        s, d = float(fsrs["s"]), float(fsrs["d"])
    interval = next_interval(s)
    return {
        "id": item.get("id"),
        "subject": item.get("subject"),
        "topic": item.get("topic"),
        "status": item.get("status"),
        "stability": round(s, 2),
        "difficulty": round(d, 2),
        "retrievability_today": round(retrievability(0.0, s), 3),
        "interval_days": interval,
        "suggested_next_date": (today + timedelta(days=interval)).isoformat(),
        "bootstrapped": bootstrapped,
    }


def schedule_queue(queue_path: Path, today: date) -> list[dict]:
    data = json.loads(queue_path.read_text(encoding="utf-8"))
    return [schedule_item(it, today) for it in data.get("items", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description="FSRS 间隔复习调度（引用 open-spaced-repetition/fsrs-rs 核心公式）")
    parser.add_argument("--queue", required=True, help="ReviewQueue 1.1 JSON 路径")
    parser.add_argument("--today", default=None, help="基准日 YYYY-MM-DD（默认系统今日）")
    args = parser.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    out = schedule_queue(Path(args.queue), today)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    raise SystemExit(main())
