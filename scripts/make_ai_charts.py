"""AI 포트폴리오 차트 — 실행 기록 파일에서 값을 읽어 라이트/다크 PNG를 만든다.

실행: python scripts/make_ai_charts.py   (필요: matplotlib, Windows의 맑은 고딕 글꼴)
읽는 곳: 이 저장소와 같은 폴더에 있는 실습 폴더(기본은 저장소의 상위 폴더,
         다른 곳이면 환경 변수 AI_PRACTICE_ROOT로 지정)
  - ai-special-skeleton/2. skeleton02/outputs/checkpoint-100/trainer_state.json  (LoRA loss)
  - ai-special-skeleton/3. skeleton03/outputs/checkpoint-100/trainer_state.json  (QLoRA loss)
  - 15th-ai1/ai-dev-deployment/mlflow.db                                         (MLflow epoch loss, 읽기 전용)
쓰는 곳: assets/ai-*.png, assets/ai-*-dark.png
"""
import json
import os
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch
from matplotlib.transforms import IdentityTransform

REPO = Path(__file__).resolve().parents[1]
FILES = Path(os.environ.get("AI_PRACTICE_ROOT", REPO.parent))
OUT = REPO / "assets"

# ---------- 폰트 ----------
FONT_DIR = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
for f in ("malgun.ttf", "malgunbd.ttf"):
    font_manager.fontManager.addfont(str(FONT_DIR / f))
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# ---------- 크기: CSS px 기준, 2배로 저장 ----------
DPI = 192                     # 1 CSS px = 2 이미지 px
def pt(px):                   # CSS px -> matplotlib point
    return px * 0.75
W_PX, H_PX = 880, 440

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
                  grid="#e1e0d9", base="#c3c2b7", s1="#2a78d6", s2="#eb6834", neutral="#898781"),
    "dark":  dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
                  grid="#2c2c2a", base="#383835", s1="#3987e5", s2="#d95926", neutral="#898781"),
}

# ---------- 데이터: 기록 파일에서 직접 읽기 ----------
def trainer_losses(path):
    st = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = [(h["step"], h["loss"]) for h in st["log_history"] if "loss" in h]
    return [s for s, _ in rows], [l for _, l in rows]

lora_steps, lora_loss = trainer_losses(FILES / "ai-special-skeleton/2. skeleton02/outputs/checkpoint-100/trainer_state.json")
qlora_steps, qlora_loss = trainer_losses(FILES / "ai-special-skeleton/3. skeleton03/outputs/checkpoint-100/trainer_state.json")

con = sqlite3.connect(f"file:{FILES / '15th-ai1/ai-dev-deployment/mlflow.db'}?mode=ro", uri=True)
runs = con.execute("SELECT run_uuid, start_time FROM runs ORDER BY start_time").fetchall()
mlflow_runs = []
for run_uuid, start in runs:
    pts = con.execute("SELECT step, value FROM metrics WHERE run_uuid=? AND key='epoch_loss' ORDER BY step", (run_uuid,)).fetchall()
    mlflow_runs.append((start, [s + 1 for s, _ in pts], [v for _, v in pts]))
con.close()

# 실행 정확도: 2026.10.07에 evaluation.py --etype exec --plug_value 로 채점한 출력값
ACC_CATS = ["easy · 44문항", "medium · 16문항", "전체 · 60문항"]
ACC_BASE = [0.682, 0.250, 0.567]
ACC_LORA = [0.773, 0.562, 0.717]

def rolling(xs, n=10):
    return [sum(xs[max(0, i - n + 1): i + 1]) / len(xs[max(0, i - n + 1): i + 1]) for i in range(len(xs))]

# ---------- 공통 틀 ----------
def frame(t, title, subtitle, legend, right_px=120):
    fig = plt.figure(figsize=(W_PX / 96, H_PX / 96), dpi=DPI, facecolor=t["surface"])
    # 머리글(제목 · 부제 · 범례)은 왼쪽 정렬, 플롯 영역은 그 아래
    fig.text(24 / W_PX, 1 - 26 / H_PX, title, fontsize=pt(17), fontweight="bold", color=t["ink"], va="top")
    fig.text(24 / W_PX, 1 - 54 / H_PX, subtitle, fontsize=pt(12.5), color=t["ink2"], va="top")
    x = 24
    for color, label, kind in legend:
        y = 1 - 86 / H_PX
        if kind == "bar":
            fig.patches.append(plt.Rectangle((x / W_PX, y - 5 / H_PX), 12 / W_PX, 10 / H_PX,
                                             transform=fig.transFigure, color=color, figure=fig))
        else:
            fig.lines.append(plt.Line2D([x / W_PX, (x + 16) / W_PX], [y, y], transform=fig.transFigure,
                                        color=color, linewidth=pt(2), solid_capstyle="round", figure=fig))
        fig.text((x + 22) / W_PX, y, label, fontsize=pt(12.5), color=t["ink"], va="center")
        x += 22 + len(label) * 9.5 + 26
    ax = fig.add_axes([64 / W_PX, 44 / H_PX, 1 - 64 / W_PX - right_px / W_PX, 1 - 44 / H_PX - 112 / H_PX])
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["base"])
    ax.spines["bottom"].set_linewidth(pt(1))
    ax.grid(axis="y", color=t["grid"], linewidth=pt(1), linestyle="-")
    ax.set_axisbelow(True)
    ax.tick_params(colors=t["muted"], labelsize=pt(12), length=0, pad=pt(8))
    return fig, ax

def rounded_columns(fig, ax, xs, heights, width, color, radius_px=4):
    """위 끝만 4px 둥글고 바닥은 각진 막대(표시 좌표에서 그림)."""
    fig.canvas.draw()
    r = radius_px * DPI / 96
    for x, h in zip(xs, heights):
        (x0, y0), (x1, y1) = ax.transData.transform([(x - width / 2, 0), (x + width / 2, h)])
        verts = [(x0, y0), (x0, y1 - r), (x0, y1), (x0 + r, y1), (x1 - r, y1), (x1, y1), (x1, y1 - r), (x1, y0), (x0, y0)]
        codes = [MPath.MOVETO, MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO, MPath.CURVE3, MPath.CURVE3, MPath.LINETO, MPath.CLOSEPOLY]
        fig.patches.append(PathPatch(MPath(verts, codes), transform=IdentityTransform(), facecolor=color, edgecolor="none", figure=fig))

def save(fig, t_name, name):
    suffix = "" if t_name == "light" else "-dark"
    path = OUT / f"{name}{suffix}.png"
    fig.savefig(path, dpi=DPI, facecolor=fig.get_facecolor())
    plt.close(fig)
    print("saved", path)

# ---------- 차트 1: 실행 정확도 ----------
def chart_accuracy(t_name):
    t = THEMES[t_name]
    fig, ax = frame(t, "Text-to-SQL 실행 정확도 — 베이스 vs LoRA",
                    "SmolLM2-360M · Spider 60문항 · LoRA 예측 2026.08.20 · 채점 2026.10.07",
                    [(t["neutral"], "베이스 모델 (강사 제공 예측)", "bar"), (t["s1"], "LoRA 적용 (직접 학습한 어댑터)", "bar")],
                    right_px=32)
    ax.set_xlim(-0.6, 2.6)
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0", "0.25", "0.50", "0.75", "1.00"])
    ax.set_xticks(range(3))
    ax.set_xticklabels(ACC_CATS)
    fig.canvas.draw()
    # 막대 24 CSS px, 이웃 막대 사이 2px 표면 간격
    px_per_unit = ax.transData.transform([(1, 0)])[0][0] - ax.transData.transform([(0, 0)])[0][0]
    bw = 24 * DPI / 96 / px_per_unit
    gap = 2 * DPI / 96 / px_per_unit
    xb = [i - bw / 2 - gap / 2 for i in range(3)]
    xl = [i + bw / 2 + gap / 2 for i in range(3)]
    rounded_columns(fig, ax, xb, ACC_BASE, bw, t["neutral"])
    rounded_columns(fig, ax, xl, ACC_LORA, bw, t["s1"])
    # 베이스 값은 막대 오른쪽 끝에 맞춰 왼쪽으로 펼쳐, 옆의 더 높은 LoRA 막대에 붙지 않게 한다
    for x, v in zip(xb, ACC_BASE):
        ax.text(x + bw / 2, v + 0.025, f"{v:.3f}", ha="right", va="bottom", fontsize=pt(12), color=t["ink2"])
    for x, v in zip(xl, ACC_LORA):
        ax.text(x, v + 0.025, f"{v:.3f}", ha="center", va="bottom", fontsize=pt(12), color=t["ink"], fontweight="bold")
    save(fig, t_name, "ai-text2sql-accuracy")

# ---------- 차트 2: 학습 loss ----------
def chart_training_loss(t_name):
    t = THEMES[t_name]
    fig, ax = frame(t, "학습 loss — LoRA 360M vs QLoRA 1.7B",
                    "두 모델 모두 400건 × 4 에폭 · 100 step · 굵은 선은 10 step 이동 평균 · 학습 지표이며 정확도가 아님",
                    [(t["s1"], "LoRA · SmolLM2-360M", "line"), (t["s2"], "QLoRA 4bit · SmolLM2-1.7B", "line")])
    for steps, loss, color, name in ((lora_steps, lora_loss, t["s1"], "LoRA 360M"), (qlora_steps, qlora_loss, t["s2"], "QLoRA 1.7B")):
        ax.plot(steps, loss, color=color, linewidth=pt(1), alpha=0.28, solid_joinstyle="round")
        smooth = rolling(loss)
        ax.plot(steps, smooth, color=color, linewidth=pt(2), solid_joinstyle="round", solid_capstyle="round")
        ax.plot([steps[-1]], [smooth[-1]], marker="o", markersize=pt(9), color=color,
                markeredgecolor=t["surface"], markeredgewidth=pt(2), zorder=5)
        ax.annotate(f"{name}  {smooth[-1]:.2f}", (steps[-1], smooth[-1]), xytext=(pt(12), 0),
                    textcoords="offset points", va="center", fontsize=pt(12), color=t["ink"])
    ax.set_xlim(0, 101)
    ax.set_ylim(0, 3.2)   # 원값 최댓값 3.05(step 3)가 잘리지 않게
    ax.set_xticks([1, 25, 50, 75, 100])
    ax.set_yticks([0, 1, 2, 3])
    ax.set_xlabel("step", fontsize=pt(12), color=t["muted"], labelpad=pt(4))
    save(fig, t_name, "ai-training-loss")

# ---------- 차트 3: MLflow epoch loss ----------
def chart_mlflow(t_name):
    t = THEMES[t_name]
    labels = ["1회차 · 07.09", "2회차 · 07.10"]
    colors = [t["s1"], t["s2"]]
    fig, ax = frame(t, "MNIST CNN epoch loss — MLflow에 기록된 두 번의 실행",
                    "Adam lr 0.001 · batch 64 · 5 에폭 · CUDA · mlflow.db에서 읽음 · 정확도는 기록하지 않았음",
                    [(c, l, "line") for c, l in zip(colors, labels)], right_px=32)
    for (start, epochs, vals), color in zip(mlflow_runs, colors):
        ax.plot(epochs, vals, color=color, linewidth=pt(2), marker="o", markersize=pt(9),
                markeredgecolor=t["surface"], markeredgewidth=pt(2), solid_joinstyle="round")
    ax.set_xlim(0.8, 5.2)
    ax.set_ylim(0, 0.2)
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_yticks([0, 0.05, 0.10, 0.15, 0.20])
    ax.set_yticklabels(["0", "0.05", "0.10", "0.15", "0.20"])
    ax.set_xlabel("epoch", fontsize=pt(12), color=t["muted"], labelpad=pt(4))
    save(fig, t_name, "ai-mlflow-loss")

if __name__ == "__main__":
    print("LoRA steps", len(lora_steps), "last10", round(sum(lora_loss[-10:]) / 10, 3))
    print("QLoRA steps", len(qlora_steps), "last10", round(sum(qlora_loss[-10:]) / 10, 3))
    for start, e, v in mlflow_runs:
        print("mlflow run", start, [round(x, 4) for x in v])
    for name in ("light", "dark"):
        chart_accuracy(name)
        chart_training_loss(name)
        chart_mlflow(name)
