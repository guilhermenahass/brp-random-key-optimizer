"""Gera um GIF do pátio a partir do log de desenho do RKO (Results/draws/draw-*).

Uso:
    python scripts/animate_yard.py cpp/Results/draws/example-draw-ILS-11801.txt docs/img/yard.gif

Formato do log (escrito por TraceBestSolution em Problem.h):
    HEIGHT 7
    INIT
    P0: 54 41 14 ...      (base -> topo)
    RELOCATE <bloco> <origem> <destino>
    EXTRACT <bloco>
"""
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import cm
from PIL import Image


def parse(path):
    height, stacks, events = 0, [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "HEIGHT":
                height = int(parts[1])
            elif parts[0].startswith("P") and parts[0].endswith(":"):
                stacks.append([int(x) for x in parts[1:]])
            elif parts[0] == "RELOCATE":
                events.append(("R", int(parts[1]), int(parts[2]), int(parts[3])))
            elif parts[0] == "EXTRACT":
                events.append(("E", int(parts[1])))
    return height, stacks, events


def draw(stacks, height, n, title, highlight=None, target=None):
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=90)
    cmap = cm.get_cmap("viridis")
    for s, stack in enumerate(stacks):
        for level, b in enumerate(stack):
            edge, lw = "#1b1b1b", 0.8
            if b == highlight:
                edge, lw = "#ff3b30", 3
            elif b == target:
                edge, lw = "#ffcc00", 3
            ax.add_patch(plt.Rectangle((s + 0.05, level + 0.05), 0.9, 0.9,
                                       facecolor=cmap(1 - b / n), edgecolor=edge, linewidth=lw))
            ax.text(s + 0.5, level + 0.5, str(b), ha="center", va="center",
                    fontsize=8, color="white" if b > n * 0.45 else "black")
    ax.set_xlim(0, len(stacks))
    ax.set_ylim(0, height)
    ax.set_xticks([s + 0.5 for s in range(len(stacks))], [f"P{s+1}" for s in range(len(stacks))])
    ax.set_yticks([])
    ax.axhline(height, color="#999", linestyle="--", linewidth=0.8)
    ax.set_title(title, fontsize=11)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.canvas.draw()
    img = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB")
    plt.close(fig)
    return img


def main(log_path, out_path):
    height, stacks, events = parse(log_path)
    n = sum(len(s) for s in stacks)
    frames, durations = [], []
    relocations, extracted = 0, 0
    frames.append(draw(stacks, height, n, f"Estado inicial: {n} blocos, {len(stacks)} pilhas, altura {height}"))
    durations.append(1500)
    for ev in events:
        if ev[0] == "R":
            _, b, src, dst = ev
            stacks[src].pop()
            stacks[dst].append(b)
            relocations += 1
            title = f"Realocação {relocations}: bloco {b}  P{src+1} → P{dst+1}"
            frames.append(draw(stacks, height, n, title, highlight=b))
            durations.append(260)
        else:
            _, b = ev
            for st in stacks:
                if st and st[-1] == b:
                    st.pop()
            extracted += 1
            # ponytail: só desenha extrações a cada 3 blocos para o GIF não ficar enorme
            if extracted % 3 == 0 or extracted == n:
                frames.append(draw(stacks, height, n, f"Retirados {extracted}/{n} | realocações: {relocations}"))
                durations.append(140)
    durations[-1] = 2500
    frames[0].save(out_path, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    print(f"{out_path}: {len(frames)} quadros, {relocations} realocações")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
