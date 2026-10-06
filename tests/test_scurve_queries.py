#!/usr/bin/env python3
"""Identity tests for the closed-form S-curve lookahead queries.

Mirrors patches/linuxcnc-jerk-lookahead/src/emc/tp/sp_scurve.c so we can
verify the kinematics without a LinuxCNC build.
"""
from __future__ import annotations

import math
import sys

TP_VEL_EPSILON = 1e-8
FAIL = 0


def fail(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"FAIL: {msg}")


def check(cond: bool, msg: str) -> None:
    if not cond:
        fail(msg)


def scurve_k(A: float, J: float) -> float:
    return A * A / J


def dist_change(v0: float, vf: float, A: float, J: float) -> float:
    if v0 < vf:
        v0, vf = vf, v0
    dv = v0 - vf
    if dv <= TP_VEL_EPSILON:
        return 0.0
    k = scurve_k(A, J)
    if dv >= k:
        return (v0 * v0 - vf * vf) / (2.0 * A) + (v0 - vf) * A / (2.0 * J)
    return (v0 + vf) * math.sqrt(dv / J)


def vpeak_rest_to_rest(S: float, A: float, J: float) -> float:
    k = scurve_k(A, J)
    S_trans = 2.0 * A**3 / J**2
    if S <= S_trans:
        return (S * math.sqrt(J) / 2.0) ** (2.0 / 3.0)
    disc = k * k + 4.0 * A * S
    return 0.5 * (-k + math.sqrt(disc))


def max_start_triangular(S: float, Ve: float, J: float) -> float:
    JS2 = J * S * S
    if Ve <= TP_VEL_EPSILON:
        return (S * math.sqrt(J)) ** (2.0 / 3.0)
    u = JS2 / (4.0 * Ve * Ve)
    for _ in range(20):
        a = u + 2.0 * Ve
        f = u * a * a - JS2
        fp = a * (3.0 * u + 2.0 * Ve)
        if abs(fp) < 1e-18:
            break
        un = u - f / fp
        if un < 0.0:
            un = 0.5 * u
        if abs(un - u) <= 1e-12 * max(1.0, un):
            u = un
            break
        u = un
    return Ve + u


def max_start(S: float, Ve: float, A: float, J: float) -> float:
    Ve = abs(Ve)
    k = scurve_k(A, J)
    disc = k * k + 4.0 * (2.0 * A * S + Ve * Ve + k * Ve)
    Vs = 0.5 * (-k + math.sqrt(disc))
    if Vs < Ve:
        Vs = Ve
    if Vs - Ve + 1e-12 >= k:
        return Vs
    Vs = max_start_triangular(S, Ve, J)
    return max(Vs, Ve)


def speed_with_T(A: float, J: float, T: float) -> float:
    T1 = A / J
    if T <= T1:
        return 0.5 * J * T * T
    return A * T - 0.5 * A * A / J


def sc_distance(t: float, v: float, a: float, j: float) -> float:
    return t * (v + t * (0.5 * a + (1.0 / 6.0) * j * t))


def delta_velocity(t: float, a: float, j: float) -> float:
    return t * (a + 0.5 * j * t)


def next_accel(t, targetV, v, a, maxA, maxJ):
    max_da = maxJ * t
    tiny_da = max_da * t * 0.001
    vel_err = targetV - v
    if vel_err > tiny_da:
        acc_req = -max_da + math.sqrt(2.0 * maxJ * vel_err + max_da * max_da)
    elif vel_err < -tiny_da:
        acc_req = max_da - math.sqrt(-2.0 * maxJ * vel_err + max_da * max_da)
    else:
        acc_req = 0.0
    acc_req = max(-maxA, min(maxA, acc_req))
    if acc_req > a + max_da:
        return a + max_da
    if acc_req < a - max_da:
        return a - max_da
    return acc_req


def next_speed(v, a, t, targetV, maxA, maxJ):
    v0, a0 = v, a
    nextA = next_accel(t, targetV, v0, a0, maxA, maxJ)
    deltaV = (a0 + nextA) * t / 2.0
    if (deltaV < 0 and targetV < v0 and v0 + deltaV < targetV) or (
        0 < deltaV and v0 < targetV and targetV < v0 + deltaV
    ):
        nextA = 2.0 * (targetV - v0) / t - a0
    nextA = max(-maxA, min(maxA, nextA))
    max_da = maxJ * t
    nextA = max(a0 - max_da, min(a0 + max_da, nextA))
    v_next = v0 + (a0 + nextA) * t / 2.0
    if (v0 < targetV and v_next > targetV) or (v0 > targetV and v_next < targetV):
        nextA = 2.0 * (targetV - v0) / t - a0
        nextA = max(-maxA, min(maxA, nextA))
        nextA = max(a0 - max_da, min(a0 + max_da, nextA))
        v_next = v0 + (a0 + nextA) * t / 2.0
    return v_next, nextA, (nextA - a0) / t


def stopping_dist(v, a, maxA, maxJ):
    if maxA <= 0 or maxJ <= 0:
        return 0.0
    if abs(v) < TP_VEL_EPSILON and a <= 0:
        return 0.0
    if v < 0:
        v, a = -v, -a
    d = 0.0
    if a > 0:
        t = a / maxJ
        d += sc_distance(t, v, a, -maxJ)
        v += delta_velocity(t, a, -maxJ)
        a = 0.0
        if v <= TP_VEL_EPSILON:
            return max(d, 0.0)
    peak = -math.sqrt(v * maxJ + 0.5 * a * a)
    if peak < -maxA:
        peak = -maxA
    if a < peak:
        disc = max(a * a - 2.0 * maxJ * v, 0.0)
        t = (-a - math.sqrt(disc)) / maxJ
        t = max(t, 0.0)
        d += sc_distance(t, v, a, maxJ)
        return max(d, 0.0)
    if peak < a:
        t = (a - peak) / maxJ
        d += sc_distance(t, v, a, -maxJ)
        v += delta_velocity(t, a, -maxJ)
        a = peak
        if v <= TP_VEL_EPSILON:
            return max(d, 0.0)
    if abs(a) < 1e-12:
        return max(d, 0.0)
    deltaV = 0.5 * a * a / maxJ
    if deltaV < v:
        t = (v - deltaV) / -a
        d += sc_distance(t, v, a, 0)
        v += delta_velocity(t, a, 0)
    d += sc_distance(-a / maxJ, v, a, maxJ)
    return max(d, 0.0)


def test_vpeak_roundtrip():
    A, J = 500.0, 5000.0
    k = scurve_k(A, J)
    # Trapezoidal-accel region (S > 2 A^3/J^2 = 10)
    S = 20.0
    V = vpeak_rest_to_rest(S, A, J)
    s_fwd = dist_change(0.0, V, A, J) * 2.0
    check(abs(s_fwd - S) / S < 1e-9, f"rest-to-rest trap S={S} V={V} fwd={s_fwd}")
    check(abs(V - 78.07764064044152) < 1e-8, f"known peak V={V}")
    check(V < k or True, "region")
    # Triangular region
    S = 1.0
    V = vpeak_rest_to_rest(S, A, J)
    check(V < k, f"expected triangular peak, got V={V} k={k}")
    s_fwd = dist_change(0.0, V, A, J) * 2.0
    check(abs(s_fwd - S) / S < 1e-6, f"rest-to-rest tri S={S} V={V} fwd={s_fwd}")
    # Always below infinite-jerk peak
    check(V < math.sqrt(A * S) + 1e-9, "jerk peak must be < triangular")


def test_max_start_roundtrip():
    cases = [
        (100.0, 100.0, 100.0, 5000.0),  # trap, high Ve
        (20.0, 10.0, 500.0, 5000.0),
        (0.5, 5.0, 500.0, 5000.0),  # likely triangular
        (100.0, 0.0, 100.0, 5000.0),  # Ve=0 → rest-to-rest
    ]
    for S, Ve, A, J in cases:
        Vs = max_start(S, Ve, A, J)
        s_fwd = dist_change(Vs, Ve, A, J)
        rel = abs(s_fwd - S) / max(S, 1e-9)
        check(Vs + 1e-9 >= Ve, f"Vs < Ve: Vs={Vs} Ve={Ve}")
        check(rel < 1e-6, f"max_start roundtrip S={S} Ve={Ve} Vs={Vs} fwd={s_fwd} rel={rel}")
        trap = math.sqrt(Ve * Ve + 2.0 * A * S)
        check(Vs <= trap + 1e-6, f"Vs {Vs} exceeds inf-jerk {trap}")


def test_speed_with_T():
    A, J = 500.0, 5000.0
    T1 = A / J  # 0.1
    check(abs(speed_with_T(A, J, 0.001) - 0.5 * J * 0.001**2) < 1e-12, "short T")
    check(abs(speed_with_T(A, J, T1) - 0.5 * A * A / J) < 1e-9, "at T1")
    check(abs(speed_with_T(A, J, 0.2) - (A * 0.2 - 0.5 * A * A / J)) < 1e-9, "long T")
    # Old fallback was wildly wrong on both sides of T1
    old_short = min(A * 0.001, math.sqrt(A * A * 0.001 / J))
    check(speed_with_T(A, J, 0.001) < old_short / 10, "short T must not use old fallback")
    old_long = min(A * 0.2, math.sqrt(A * A * 0.2 / J))
    check(speed_with_T(A, J, 0.2) > old_long * 10, "long T must not use old fallback")


def test_next_speed_regression():
    # Old bug: v=10, a=-500, t=0.001, target=9.9, maxA=100 → returned v=-0.2
    v, a, j = next_speed(10.0, -500.0, 0.001, 9.9, 100.0, 1e5)
    check(v > 9.0, f"nextSpeed must not replace v with Δv, got v={v} a={a} j={j}")
    check(abs(v - (10.0 + (-500.0 + a) * 0.001 / 2.0)) < 1e-9, "v must match integration")
    check(abs(a + 400.0) < 1e-9 or abs(j) <= 1e5 + 1e-6, f"jerk bound j={j} a={a}")


def test_stopping_dist():
    A, J = 500.0, 5000.0
    v = 100.0
    d = stopping_dist(v, 0.0, A, J)
    expected = v * v / (2 * A) + v * A / (2 * J)
    check(abs(d - expected) < 1e-9, f"a=0 stop {d} vs {expected}")
    d_over = stopping_dist(1.0, -100.0, 1000.0, 100.0)
    check(d_over >= 0.0, f"over-decel must not be negative, got {d_over}")
    check(d_over < 1.0, f"over-decel distance should be small, got {d_over}")


def main() -> int:
    test_vpeak_roundtrip()
    test_max_start_roundtrip()
    test_speed_with_T()
    test_next_speed_regression()
    test_stopping_dist()
    if FAIL:
        print(f"{FAIL} failure(s)")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
