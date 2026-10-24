"""Exact Shapley attribution (Shapley 1953) of a stress loss to risk-factor groups.

Players are the shock components of a stress scenario. The coalition value v(S) is the change of an outcome
(e.g. mean real profit, % of purchase value) when ONLY the components in S are switched on, evaluated on the SAME
simulated paths (common random numbers). With n players the exact value needs 2^n coalition evaluations (n<=6 -> 64),
so no sampling approximation is used.

    phi_i = sum_{S not containing i}  |S|! (n-|S|-1)! / n!  * ( v(S + i) - v(S) )

Properties (unit-tested): efficiency  sum_i phi_i = v(N) - v(empty);  null player (a component with no effect gets 0);
symmetry (identical players get equal values)."""
from __future__ import annotations

from itertools import combinations
from math import factorial
from typing import Callable, Hashable, Sequence


def shapley(players: Sequence[Hashable], value: Callable[[frozenset], float]) -> dict:
    """Exact Shapley values. `value(frozenset)` must return v(S); v(empty) is the baseline."""
    n = len(players)
    cache: dict[frozenset, float] = {}

    def v(s: frozenset) -> float:
        if s not in cache:
            cache[s] = float(value(s))
        return cache[s]

    phi = {p: 0.0 for p in players}
    for p in players:
        others = [q for q in players if q != p]
        for k in range(n):
            w = factorial(k) * factorial(n - k - 1) / factorial(n)
            for comb in combinations(others, k):
                s = frozenset(comb)
                phi[p] += w * (v(s | {p}) - v(s))
    total = v(frozenset(players)) - v(frozenset())
    return {"phi": phi, "total": total, "baseline": v(frozenset()), "full": v(frozenset(players)),
            "efficiency_gap": float(sum(phi.values()) - total), "n_evals": len(cache)}
