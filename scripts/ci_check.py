"""Confere a saída do RKO no CI: a solução existe, é viável e bate com o log."""
import pathlib
import sys

res = pathlib.Path("cpp/Results/Results_RKO.csv").read_text().strip().splitlines()
assert res, "Results_RKO.csv vazio"
campos = res[-1].split("\t")
melhor = float(campos[5])
draws = sorted(pathlib.Path("cpp/Results/draws").glob("draw-*"))
assert draws, "log da melhor solução não foi gerado"
log = draws[-1].read_text().splitlines()
realoc = sum(1 for l in log if l.startswith("RELOCATE"))
extr = sum(1 for l in log if l.startswith("EXTRACT"))
n = sum(len(l.split(":")[1].split()) for l in log if l.startswith("P") and ":" in l)
print(f"instância {campos[2]}: {n} blocos, melhor = {melhor:.0f} realocações, log = {realoc} realocações e {extr} retiradas")
assert extr == n, "nem todos os blocos foram retirados"
assert realoc == int(melhor), "o log não bate com o custo da solução"
assert melhor < 1_000_000, "solução inviável (deadlock)"
