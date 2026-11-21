"""由分析结果 CSV 生成图表（PNG，供 README 引用）。"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无界面环境 / CI 也能出图
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

# 中文标注：优先系统自带字体，找不到时退回 DejaVu Sans（英文仍正常）
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "WenQuanYi Zen Hei",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.25
plt.rcParams["grid.linestyle"] = "--"

PALETTE = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"]


def _wan(value: float, _position: int | None = None) -> str:
    """把大数字渲染成「万 / 亿」，避免坐标轴出现 1e8 之类的科学计数偏移。

    精度按量级递进，否则 1.5 万 / 2.0 万会一起变成「2万」，刻度重复。
    """
    magnitude = abs(value)
    if magnitude >= 1e8:
        return f"{value / 1e8:g}亿"
    if magnitude >= 1e7:
        return f"{value / 1e4:,.0f}万"
    if magnitude >= 1e4:
        return f"{value / 1e4:,.1f}万".replace(".0万", "万")
    return f"{value:,.0f}"


def _use_wan(axis) -> None:
    axis.set_major_formatter(FuncFormatter(_wan))


def _load(results_dir: Path, name: str) -> pd.DataFrame | None:
    path = results_dir / f"{name}.csv"
    if not path.is_file():
        return None
    frame = pd.read_csv(path)
    return frame if not frame.empty else None


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def plot_hourly(results_dir: Path, fig_dir: Path) -> Path | None:
    """24 小时活跃曲线：点击量 vs 购买量。"""
    frame = _load(results_dir, "hourly_activity")
    if frame is None:
        return None

    fig, ax = plt.subplots(figsize=(10, 4.6))
    line = ax.plot(
        frame["hour"], frame["pv"], marker="o", ms=3.5, lw=1.8, color=PALETTE[0], label="点击 PV"
    )[0]
    ax.set_xlabel("小时（北京时间）")
    ax.set_ylabel("点击量 PV", color=PALETTE[0])
    ax.set_xticks(range(0, 24, 2))
    _use_wan(ax.yaxis)

    ax2 = ax.twinx()
    bars = ax2.bar(frame["hour"], frame["buy"], color=PALETTE[1], alpha=0.35, label="购买 Buy")
    ax2.set_ylabel("购买次数", color=PALETTE[1], labelpad=10)
    ax2.spines["right"].set_visible(True)
    ax2.grid(False)
    _use_wan(ax2.yaxis)

    ax.set_title("24 小时活跃分布：点击高峰与成交高峰并不同步")
    ax.legend(
        [line, bars],
        ["点击 PV", "购买 Buy"],
        loc="upper left",
        frameon=False,
        fontsize=9,
    )
    return _save(fig, fig_dir / "hourly_activity.png")


def plot_daily(results_dir: Path, fig_dir: Path) -> Path | None:
    """每日 PV 柱状 + UV 折线。"""
    frame = _load(results_dir, "daily_traffic")
    if frame is None:
        return None

    fig, ax = plt.subplots(figsize=(10, 4.6))
    bars = ax.bar(frame["day"], frame["pv"], color=PALETTE[0], alpha=0.75, label="PV")
    ax.set_ylabel("PV")
    ax.set_xlabel("日期")
    ax.tick_params(axis="x", rotation=35)
    _use_wan(ax.yaxis)

    ax2 = ax.twinx()
    line = ax2.plot(frame["day"], frame["uv"], marker="o", lw=2, color=PALETTE[3], label="UV")[0]
    ax2.set_ylabel("UV", color=PALETTE[3], labelpad=10)
    ax2.set_ylim(0, frame["uv"].max() * 1.08)  # 从 0 起，避免双轴夸大涨幅
    ax2.spines["right"].set_visible(True)
    ax2.grid(False)
    _use_wan(ax2.yaxis)

    ax.set_title("每日流量走势（2017-11-25 ~ 2017-12-03）")
    ax2.legend([bars, line], ["PV（左轴）", "UV（右轴）"], loc="upper left", frameon=False, fontsize=9)
    return _save(fig, fig_dir / "daily_traffic.png")


def plot_funnel(results_dir: Path, fig_dir: Path) -> Path | None:
    """转化漏斗：行为级 PV → 收藏+加购 → 购买。"""
    frame = _load(results_dir, "funnel")
    if frame is None:
        return None

    row = frame.iloc[0]
    stages = ["点击 PV", "收藏+加购", "购买 Buy"]
    values = [float(row["pv"]), float(row["fav_cart"]), float(row["buy"])]

    fig, ax = plt.subplots(figsize=(8, 4.2))
    bars = ax.barh(stages[::-1], values[::-1], color=[PALETTE[2], PALETTE[1], PALETTE[0]])
    ax.set_xlabel("行为次数")
    ax.set_xlim(0, max(values) * 1.18)
    _use_wan(ax.xaxis)

    for bar, value in zip(bars, values[::-1]):
        ax.text(
            value + max(values) * 0.015,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,.0f}",
            va="center",
            fontsize=9,
        )

    ax.set_title(
        f"行为转化漏斗  PV→收藏加购 {row['pv_to_favcart']:.2%} ｜ "
        f"收藏加购→购买 {row['favcart_to_buy']:.2%} ｜ PV→购买 {row['pv_to_buy']:.2%}"
    )
    return _save(fig, fig_dir / "funnel.png")


def plot_behavior(results_dir: Path, fig_dir: Path) -> Path | None:
    """行为类型占比。"""
    frame = _load(results_dir, "behavior_distribution")
    if frame is None:
        return None

    order = ["pv", "cart", "fav", "buy"]
    frame = frame.set_index("behavior_type").reindex([b for b in order if b in set(frame["behavior_type"])]).reset_index()

    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    bars = ax.bar(frame["behavior_type"], frame["events"], color=PALETTE[: len(frame)])
    ax.set_ylabel("行为次数")
    ax.set_title("行为类型分布")
    _use_wan(ax.yaxis)

    for bar, value, share in zip(bars, frame["events"], frame["share"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value * 1.01,
            f"{value:,.0f}\n({share:.2%})",
            ha="center",
            va="bottom",
            fontsize=8.5,
        )
    ax.set_ylim(0, frame["events"].max() * 1.18)
    return _save(fig, fig_dir / "behavior_distribution.png")


def plot_categories(results_dir: Path, fig_dir: Path) -> Path | None:
    """成交额（次数）最高的类目。"""
    frame = _load(results_dir, "top_categories")
    if frame is None:
        return None

    frame = frame.sort_values("buy")
    fig, ax = plt.subplots(figsize=(9, 4.6))
    bars = ax.barh(frame["category_id"].astype(str), frame["buy"], color=PALETTE[0])
    ax.set_xlabel("购买次数")
    ax.set_ylabel("类目 ID", labelpad=6)
    ax.set_title("购买次数 Top 10 商品类目")
    ax.set_xlim(0, frame["buy"].max() * 1.12)
    _use_wan(ax.xaxis)
    for bar, value in zip(bars, frame["buy"]):
        ax.text(
            value + frame["buy"].max() * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{value:,.0f}",
            va="center",
            fontsize=8.5,
        )
    return _save(fig, fig_dir / "top_categories.png")


def plot_rfm_matrix(results_dir: Path, fig_dir: Path) -> Path | None:
    """RFM 5×5 分群热力图：人数越多颜色越深。"""
    frame = _load(results_dir, "rfm_segments")
    if frame is None:
        return None

    pivot = (
        frame.pivot(index="f_score", columns="r_score", values="users")
        .reindex(index=range(5, 0, -1), columns=range(1, 6))
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(7.4, 5.6))
    ax.grid(False)
    image = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(range(pivot.shape[1]))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(pivot.shape[0]))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("R 得分（距最后一次购买，5 = 最近）")
    ax.set_ylabel("F 得分（购买频次，5 = 最频繁）")
    ax.set_title("RFM 人群结构：右上角是高价值客户")

    threshold = pivot.values.max() * 0.55
    for row in range(pivot.shape[0]):
        for col in range(pivot.shape[1]):
            value = pivot.values[row, col]
            ax.text(
                col,
                row,
                f"{value:,.0f}",
                ha="center",
                va="center",
                fontsize=8.5,
                color="white" if value > threshold else "#333333",
            )

    fig.colorbar(image, ax=ax, label="用户数")
    return _save(fig, fig_dir / "rfm_segments.png")


PLOTTERS = (
    plot_daily,
    plot_hourly,
    plot_funnel,
    plot_behavior,
    plot_categories,
    plot_rfm_matrix,
)


def build_all(results_dir: str | Path = "results", fig_dir: str | Path | None = None) -> list[Path]:
    """生成全部图表，返回已写出的文件列表。"""
    results_dir = Path(results_dir)
    fig_dir = Path(fig_dir) if fig_dir else results_dir / "figures"

    produced: list[Path] = []
    for plotter in PLOTTERS:
        path = plotter(results_dir, fig_dir)
        if path is not None:
            produced.append(path)
    return produced
