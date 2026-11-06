# brp_rko.py
# Random-Key Optimizer (RKO) + Block Relocation Problem (BRP)
# Executa uma instância de brinquedo e salva:
#  - brp_yard_initial.png, brp_yard_mid.png, brp_yard_final.png (se matplotlib disponível)
#  - brp_moves.csv  (sequência de realocações)
#  - imprime no console o nº de realocações e algumas estatísticas

from __future__ import annotations
import math, random, time, csv, os
from dataclasses import dataclass
from typing import List, Tuple, Optional

# Matplotlib é opcional (só para visual)
try:
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except Exception:
    _HAS_MPL = False


# =========================================================
# 1) Definições do problema BRP
# =========================================================

@dataclass
class BRPInstance:
    stacks: List[List[int]]  # pilhas; TOPO no final da lista (ex.: [fundo,...,topo])
    H: int                   # capacidade máxima por pilha

def clone_stacks(stacks: List[List[int]]) -> List[List[int]]:
    return [s[:] for s in stacks]

def yard_blocks(stacks: List[List[int]]) -> List[int]:
    out: List[int] = []
    for s in stacks: out.extend(s)
    return out

def next_target_priority(stacks: List[List[int]]) -> int:
    """Menor prioridade ainda presente no pátio (sai primeiro)."""
    return min(yard_blocks(stacks))

def find_block(stacks: List[List[int]], b: int) -> Tuple[int, int]:
    """Retorna (idx_pilha, idx_posicao) de b; posição 0 é o fundo, -1 é topo."""
    for i, s in enumerate(stacks):
        for j, val in enumerate(s):
            if val == b:
                return i, j
    return -1, -1

def feasible_destinations(stacks: List[List[int]], H: int) -> List[int]:
    """Pilhas com espaço disponível."""
    return [i for i, s in enumerate(stacks) if len(s) < H]

def safe_destination(stacks: List[List[int]], b: int, H: int) -> List[int]:
    """Pilhas 'seguras': vazias ou cujo topo tem prioridade MAIOR que b."""
    cand = []
    for i, s in enumerate(stacks):
        if len(s) >= H:
            continue
        if len(s) == 0 or s[-1] > b:
            cand.append(i)
    return cand

def brp_score_destination(stacks: List[List[int]], dest: int, b: int, H: int, key_b: float) -> float:
    """
    Score simples para ranquear pilha destino:
      - penaliza bloquear alguém mais prioritário (topo < b)
      - penaliza pilha quase cheia
      - ruído pequeno usando a random-key do bloco (desempate)
    Menor score é melhor.
    """
    s = stacks[dest]
    pen_block = 1.0 if (len(s) > 0 and s[-1] < b) else 0.0
    pen_full = (len(s) / max(1, H)) * 0.5
    jitter = 0.05 * key_b
    return pen_block + pen_full + jitter


# =========================================================
# 2) Decodificador BRP (usa random-keys por bloco)
# =========================================================

def decode_brp_random_keys(keys: List[float], inst: BRPInstance) -> Tuple[List[Tuple[int,int,int]], int]:
    """
    Decodificador BRP: remove sempre o menor alvo presente.
    Se o alvo está bloqueado, realoca do topo p/ baixo os bloqueadores.
    keys: vetor de tamanho N (N = número total de blocos). A chave do bloco b está em keys[b-1].
    Retorna (moves, reloc), onde moves é uma lista de (bloco, src, dst).
    """
    stacks = clone_stacks(inst.stacks)
    H = inst.H
    moves: List[Tuple[int,int,int]] = []
    reloc = 0

    # Sanidade: prioridades devem ser únicas e começar em 1
    all_blocks = yard_blocks(stacks)
    if len(set(all_blocks)) != len(all_blocks) or min(all_blocks) != 1:
        raise ValueError("As prioridades devem ser únicas e começar em 1 (1..N).")

    while len(yard_blocks(stacks)) > 0:
        tgt = next_target_priority(stacks)
        i, j = find_block(stacks, tgt)
        # alvo no topo -> expedir
        if j == len(stacks[i]) - 1:
            stacks[i].pop()
            continue

        # alvo bloqueado -> realocar bloqueadores (topo -> até liberar j)
        while len(stacks[i]) - 1 > j:
            b = stacks[i][-1]  # bloqueador atual
            # candidatos preferidos (seguros)
            C_safe = safe_destination(stacks, b, H)
            if i in C_safe:
                C_safe.remove(i)
            if len(C_safe) == 0:
                C = feasible_destinations(stacks, H)
                if i in C:
                    C.remove(i)
            else:
                C = C_safe

            if len(C) == 0:
                # fallback muito raro (se instância e H forem consistentes)
                # tenta qualquer pilha com espaço
                C = feasible_destinations(stacks, H)
                if i in C:
                    C.remove(i)
                if len(C) == 0:
                    raise RuntimeError("Sem destino viável para realocação (verifique H e instância).")

            # ranquear destinos por score (menor melhor)
            scored: List[Tuple[float,int]] = []
            key_b = keys[b-1] if 1 <= b <= len(keys) else random.random()
            for d in C:
                scored.append((brp_score_destination(stacks, d, b, H, key_b), d))
            scored.sort(key=lambda t: t[0])
            dst = scored[0][1]

            # aplicar movimento
            stacks[i].pop()
            stacks[dst].append(b)
            moves.append((b, i, dst))
            reloc += 1

        # alvo liberado -> expedir
        stacks[i].pop()

    return moves, reloc


# =========================================================
# 3) RKO: núcleo (pool, shaking, blending, busca local parcial)
# =========================================================

class RKOSolution:
    def __init__(self, keys: List[float], cost: float):
        self.keys = keys[:]
        self.cost = float(cost)

class RKO:
    """
    Framework minimalista inspirado no RKO:
    - soluções são vetores em [0,1)
    - pool de elite com proteção contra clones
    - operators: shaking, blending
    - busca local (RVND parcial: swap + mirror nas chaves)
    - metaheurísticas: SA + GA (simples) em cooperação via pool
    """
    def __init__(self, vec_len: int, eval_func, decode_func=None, pool_size=32, seed: Optional[int] = None):
        self.n = vec_len
        self.eval = eval_func            # eval(keys) -> custo
        self.decode = decode_func        # opcional; não é usada no loop interno
        self.pool_size = pool_size
        self.pool: List[RKOSolution] = []
        if seed is not None:
            random.seed(seed)

    # --- utilidades ---
    def random_keys(self) -> List[float]:
        return [random.random() for _ in range(self.n)]

    def evaluate(self, keys: List[float]) -> float:
        return float(self.eval(keys))

    def insert_pool(self, keys: List[float]):
        cost = self.evaluate(keys)
        cand = RKOSolution(keys, cost)
        # clone check leve: custo + prefixo arredondado
        signature = (round(cost, 12), tuple(round(k, 4) for k in keys[:min(10, len(keys))]))
        for s in self.pool:
            sig2 = (round(s.cost, 12), tuple(round(k, 4) for k in s.keys[:min(10, len(s.keys))]))
            if signature == sig2:
                keys = self.shake(keys, beta=0.05)
                cost = self.evaluate(keys)
                cand = RKOSolution(keys, cost)
                break

        self.pool.append(cand)
        self.pool.sort(key=lambda s: s.cost)
        if len(self.pool) > self.pool_size:
            self.pool = self.pool[:self.pool_size]

    def best(self) -> RKOSolution:
        return min(self.pool, key=lambda s: s.cost)

    # --- operadores ---
    def shake(self, keys: List[float], beta: float) -> List[float]:
        out = keys[:]
        for i in range(len(out)):
            if random.random() < 0.5:
                delta = (random.random() * 2 - 1) * beta
                v = out[i] + delta
                # wrap para [0,1)
                if v < 0.0: v += 1.0
                if v >= 1.0: v -= 1.0
                out[i] = v
        return out

    def blend(self, a: List[float], b: List[float], alpha: Optional[float] = None, noise: float = 0.01) -> List[float]:
        if alpha is None:
            alpha = random.random()
        out = []
        for i in range(self.n):
            v = alpha * a[i] + (1 - alpha) * b[i] + (random.random() * 2 - 1) * noise
            out.append(v % 1.0)
        return out

    # --- busca local: RVND parcial (swap + mirror) ---
    def ls_swap(self, keys: List[float]) -> Tuple[List[float], float]:
        base_cost = self.evaluate(keys)
        best_keys, best_cost = keys, base_cost
        n = self.n
        idx = list(range(n))
        random.shuffle(idx)
        # limite de vizinhança por iteração
        for ii in idx[:min(100, n)]:
            jj = random.randrange(n)
            if jj == ii:
                continue
            cand = keys[:]
            cand[ii], cand[jj] = cand[jj], cand[ii]
            c = self.evaluate(cand)
            if c < best_cost:
                best_keys, best_cost = cand, c
        return best_keys, best_cost

    def ls_mirror(self, keys: List[float]) -> Tuple[List[float], float]:
        base_cost = self.evaluate(keys)
        best_keys, best_cost = keys, base_cost
        n = self.n
        i = random.randrange(n - 1)
        j = random.randrange(i + 1, n)
        cand = keys[:]
        cand[i:j] = list(reversed(cand[i:j]))
        c = self.evaluate(cand)
        if c < best_cost:
            best_keys, best_cost = cand, c
        return best_keys, best_cost

    def rvnd(self, keys: List[float]) -> Tuple[List[float], float]:
        neighborhoods = [self.ls_swap, self.ls_mirror]
        random.shuffle(neighborhoods)
        improved = True
        best_keys = keys[:]
        best_cost = self.evaluate(best_keys)
        while improved:
            improved = False
            for op in neighborhoods:
                cand_keys, cand_cost = op(best_keys)
                if cand_cost < best_cost:
                    best_keys, best_cost = cand_keys, cand_cost
                    improved = True
                    random.shuffle(neighborhoods)
                    break
        return best_keys, best_cost

    # --- metaheurísticas ---
    def run_SA(self, iters=800, T0=0.1, Tend=1e-5, beta_shake=0.05):
        keys = self.pool[random.randrange(len(self.pool))].keys[:] if self.pool else self.random_keys()
        cost = self.evaluate(keys)
        best_keys, best_cost = keys[:], cost
        for t in range(1, iters + 1):
            T = T0 * (Tend / T0) ** (t / iters)
            cand = self.shake(keys, beta=beta_shake)
            # chance de aplicar RVND leve
            if random.random() < 0.35:
                cand, ccost = self.rvnd(cand)
            else:
                ccost = self.evaluate(cand)
            d = ccost - cost
            if d < 0 or random.random() < math.exp(-d / max(T, 1e-9)):
                keys, cost = cand, ccost
                if cost < best_cost:
                    best_keys, best_cost = keys[:], cost
                    self.insert_pool(best_keys)
        return best_keys, best_cost

    def run_GA(self, generations=40, pop_size=32, elite_frac=0.25, mut_beta=0.03):
        pop = [self.random_keys() for _ in range(pop_size)]
        scored = [(self.evaluate(k), k) for k in pop]
        scored.sort()
        self.insert_pool(scored[0][1])

        elite_n = max(2, int(elite_frac * pop_size))
        for _ in range(generations):
            scored.sort()
            elites = [k for (_, k) in scored[:elite_n]]
            children: List[List[float]] = []
            while len(children) < pop_size - elite_n:
                a, b = random.sample(elites, 2)
                child = self.blend(a, b, noise=0.02)
                if random.random() < 0.5:
                    child = self.shake(child, mut_beta)
                children.append(child)
            pop = elites + children
            scored = [(self.evaluate(k), k) for k in pop]
            # LS no melhor atual (probabilística)
            bcost, bkeys = scored[0][0], scored[0][1]
            if random.random() < 0.5:
                bkeys2, bcost2 = self.rvnd(bkeys)
                if bcost2 < bcost:
                    scored[0] = (bcost2, bkeys2)
            self.insert_pool(scored[0][1])

        best_cost, best_keys = min(scored, key=lambda t: t[0])
        return best_keys, best_cost


# =========================================================
# 4) Instâncias, avaliação e execução BRP com RKO
# =========================================================

def brp_instance_toy() -> BRPInstance:
    """
    Instância mais desafiadora para testar realocações.
    Cada lista é uma pilha: [fundo -> topo].
    Bloco 1 (mais prioritário) começa bloqueado por 5 e 4.
    """
    stacks = [
        [7, 3, 6],   # pilha 0 (topo = 6)
        [1, 5, 4],   # pilha 1 (1 está no fundo, bloqueado por 5 e 4)
        [8],         # pilha 2
        [2]          # pilha 3
    ]
    return BRPInstance(stacks=stacks, H=4)


def brp_eval_cost_from_keys(keys: List[float], inst: BRPInstance) -> float:
    """Função objetivo: nº de realocações."""
    _, reloc = decode_brp_random_keys(keys, inst)
    return float(reloc)

def run_brp_with_rko(time_limit=2.0, inst: Optional[BRPInstance] = None, seed=123):
    """
    Executa o RKO no BRP; retorna (instância, moves, reloc, rounds).
    """
    random.seed(seed)
    if inst is None:
        inst = brp_instance_toy()
    N = len(yard_blocks(inst.stacks))
    if N == 0:
        raise ValueError("Instância vazia.")

    # RKO com evaluate(keys) chamando diretamente o decoder do BRP
    rko = RKO(vec_len=N, eval_func=lambda keys: brp_eval_cost_from_keys(keys, inst),
              decode_func=None, pool_size=24, seed=seed)

    # Inicialização do pool
    for _ in range(24):
        rko.insert_pool(rko.random_keys())

    # Loop SA + GA até time_limit
    t0 = time.time()
    rounds = 0
    while time.time() - t0 < time_limit:
        rko.run_SA(iters=600, T0=0.1, Tend=1e-5, beta_shake=0.05)
        rko.run_GA(generations=40, pop_size=32, elite_frac=0.25, mut_beta=0.03)
        rounds += 1

    best = rko.best()
    best_moves, best_reloc = decode_brp_random_keys(best.keys, inst)
    return inst, best_moves, int(best_reloc), rounds


# =========================================================
# 5) Visualização e export (PNG e CSV)
# =========================================================

def brp_plot_yard(stacks: List[List[int]], title=None, save_path: Optional[str] = None):
    if not _HAS_MPL:
        print("[AVISO] matplotlib não disponível — pulando gráfico:", title)
        return
    W = len(stacks)
    H = max((len(s) for s in stacks), default=0)
    plt.figure(figsize=(1.5 * max(W, 1) + 1, 1.2 * max(H, 1) + 2))
    ax = plt.gca()
    for i, s in enumerate(stacks):
        for h, b in enumerate(s):  # h=0 é fundo
            rect = plt.Rectangle((i - 0.35, h), 0.7, 1.0, fill=True, alpha=0.6)
            ax.add_patch(rect)
            ax.text(i, h + 0.5, str(b), ha='center', va='center', fontsize=9)
        frame = plt.Rectangle((i - 0.4, 0), 0.8, max(H, len(s)) + 0.2, fill=False, lw=1.2)
        ax.add_patch(frame)
        ax.text(i, -0.6, f"P{i}", ha='center', va='top')
    plt.xlim(-1, W)
    plt.ylim(-1, max(H, 1) + 1)
    if title:
        plt.title(title)
    plt.axis('off')
    if save_path:
        plt.savefig(save_path, dpi=160, bbox_inches='tight')
    plt.show()

def brp_apply_moves(inst: BRPInstance, moves: List[Tuple[int,int,int]], upto: Optional[int] = None) -> List[List[int]]:
    stacks = clone_stacks(inst.stacks)
    upto = len(moves) if upto is None else min(upto, len(moves))
    for k in range(upto):
        b, src, dst = moves[k]
        assert stacks[src] and stacks[src][-1] == b, f"Movimento inválido em k={k}: topo src != b"
        stacks[src].pop()
        stacks[dst].append(b)
    # Apenas visual: expede alvos triviais após as realocações aplicadas
    changed = True
    while changed:
        changed = False
        if len(yard_blocks(stacks)) == 0: break
        tgt = next_target_priority(stacks)
        i, j = find_block(stacks, tgt)
        if j == len(stacks[i]) - 1:
            stacks[i].pop()
            changed = True
    return stacks

def brp_save_moves_csv(moves: List[Tuple[int,int,int]], path="brp_moves.csv") -> str:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["step", "block", "src", "dst"])
        for k, (b, s, d) in enumerate(moves, start=1):
            w.writerow([k, b, s, d])
    return os.path.abspath(path)


# =========================================================
# 6) __main__: executa demo, salva CSV e PNGs
# =========================================================

if __name__ == "__main__":
    # --- Defina sua instância aqui (ou use a toy) ---
    inst = brp_instance_toy()
    # Exemplo de como trocar por uma instância sua:
    # inst = BRPInstance(
    #     stacks=[
    #         [7, 3],      # pilha 0
    #         [6, 5, 1],   # pilha 1
    #         [4, 2],      # pilha 2
    #         [8]          # pilha 3
    #     ],
    #     H=4
    # )

    # Guarda cópia para snapshots
    inst0 = BRPInstance(stacks=clone_stacks(inst.stacks), H=inst.H)

    # Executa RKO no BRP
    inst, best_moves, best_cost, rounds = run_brp_with_rko(time_limit=2.0, inst=inst, seed=123)

    print("\n--- Movimentos realizados ---")
    for k, (b, s, d) in enumerate(best_moves, start=1):
        print(f"Movimento {k:02d}: bloco {b}  de P{s} -> P{d}")
    print("------------------------------\n")


    # Snapshots (inicial, meio do caminho, final)
    mid = max(0, len(best_moves) // 2)
    snap0 = inst0.stacks
    snapM = brp_apply_moves(inst0, best_moves, upto=mid)
    snapF = brp_apply_moves(inst0, best_moves, upto=len(best_moves))

    # Plota (se matplotlib disponível)
    brp_plot_yard(snap0, title=f"BRP - Pátio Inicial (H={inst.H})", save_path="brp_yard_initial.png")
    brp_plot_yard(snapM, title=f"BRP - Após {mid} realocações", save_path="brp_yard_mid.png")
    brp_plot_yard(snapF, title=f"BRP - Final após {len(best_moves)} realocações", save_path="brp_yard_final.png")

    # CSV de movimentos
    csv_abs = brp_save_moves_csv(best_moves, path="brp_moves.csv")

    # Relato no console
    print(f"[BRP] realocações = {best_cost} | rounds = {rounds}")
    print("Arquivos gerados:")
    if _HAS_MPL:
        print("  - brp_yard_initial.png")
        print("  - brp_yard_mid.png")
        print("  - brp_yard_final.png")
    else:
        print("  - (sem PNGs; matplotlib não instalado)")
    print("  -", csv_abs)
