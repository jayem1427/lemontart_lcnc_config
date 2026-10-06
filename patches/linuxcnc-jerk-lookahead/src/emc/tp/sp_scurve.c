/*!
********************************************************************
* Description: sp_scurve.c
*\brief Closed-form S-curve limit queries plus legacy simple_tp helpers
*
*\author Derived from a work by Yang Yang
*
* License: GPL Version 2
* System: Linux
*
* Copyright (c) 2004 All rights reserved.
*
* Last change:
********************************************************************/
#include <rtapi.h>
#include <rtapi_math.h>

#include "sp_scurve.h"
#include "tp_types.h"
#include "ruckig_wrapper.h"

#ifndef __KERNEL__
#include <stdio.h>
#include <string.h>
#endif

/* ========== Cached Ruckig planner ==========
 * Kept for tpSetCycleTime / interpolator compatibility. Limit queries no
 * longer call Ruckig; they use the closed-form helpers below.
 */
static RuckigPlanner cached_planner = NULL;
static double cached_cycle_time = 0.0;

int sp_scurve_init(double cycle_time) {
    if (cycle_time <= 0.0) {
        rtapi_print_msg(RTAPI_MSG_ERR, "sp_scurve_init: invalid cycle_time=%f\n", cycle_time);
        return -1;
    }

    if (cached_planner != NULL && fabs(cached_cycle_time - cycle_time) < 1e-12) {
        return 0;
    }

    if (cached_planner != NULL) {
        rtapi_print_msg(RTAPI_MSG_INFO, "sp_scurve_init: cycle time changed from %f to %f, recreating planner\n",
                        cached_cycle_time, cycle_time);
        ruckig_destroy(cached_planner);
        cached_planner = NULL;
    }

    cached_planner = ruckig_create(cycle_time);
    if (cached_planner == NULL) {
        rtapi_print_msg(RTAPI_MSG_ERR, "sp_scurve_init: ruckig_create() failed with cycle_time=%f\n", cycle_time);
        return -1;
    }

    ruckig_set_logging(cached_planner, 0);
    cached_cycle_time = cycle_time;
    rtapi_print_msg(RTAPI_MSG_INFO, "sp_scurve_init: planner created with cycle_time=%f (logging disabled)\n", cycle_time);
    return 0;
}

void sp_scurve_cleanup(void) {
    if (cached_planner != NULL) {
        ruckig_destroy(cached_planner);
        cached_planner = NULL;
        cached_cycle_time = 0.0;
    }
}

/* ================================================================
 * Closed-form 1-D S-curve queries (a0 = af = 0)
 *
 * Integrals at constant jerk J:
 *   a = a0 + J t
 *   v = v0 + a0 t + (1/2) J t^2
 *   s = v0 t + (1/2) a0 t^2 + (1/6) J t^3
 *
 * Speed-up from rest to cruise (and the reverse for a stop):
 *   T1 = A/J,  k = A^2/J  (velocity in the two jerk ramps)
 *   v  = k + A T2          if v >= k  (plateau at A)
 *   v  = J T1^2            if v <  k  (triangular, T2 = 0)
 * ================================================================ */

static double scurve_k(double maxA, double maxJ) {
    return maxA * maxA / maxJ;
}

/* x^(1/3) via Newton; avoids pow() in kernel builds. */
static double scurve_cbrt(double x) {
    double y;
    int i;
    if (x <= 0.0) {
        return 0.0;
    }
    y = (x > 1.0) ? x : 1.0;
    for (i = 0; i < 25; ++i) {
        y = (2.0 * y + x / (y * y)) / 3.0;
    }
    return y;
}

/* x^(2/3) */
static double scurve_pow23(double x) {
    double c = scurve_cbrt(x);
    return c * c;
}

/* Distance to change speed from v0 to vf, both >= 0, a0 = af = 0. */
static double scurve_dist_speed_change(double v0, double vf, double maxA, double maxJ) {
    if (v0 < vf) {
        double tmp = v0;
        v0 = vf;
        vf = tmp;
    }
    double dv = v0 - vf;
    if (dv <= TP_VEL_EPSILON) {
        return 0.0;
    }
    double k = scurve_k(maxA, maxJ);
    if (dv >= k) {
        /* Plateau at A: stop(v0) - stop(vf) with trapezoidal-accel formula */
        return (v0 * v0 - vf * vf) / (2.0 * maxA) + (v0 - vf) * maxA / (2.0 * maxJ);
    }
    /* Triangular: s = (v0 + vf) * sqrt(dv / J) */
    return (v0 + vf) * sqrt(dv / maxJ);
}

/* Rest-to-rest peak speed in distance S. */
static int scurve_vpeak_rest_to_rest(double S, double maxA, double maxJ, double *req_v) {
    double k = scurve_k(maxA, maxJ);
    /* At V = k, S_trans = 2 A^3 / J^2 */
    double S_trans = 2.0 * maxA * maxA * maxA / (maxJ * maxJ);
    if (S <= S_trans) {
        /* S = 2 V^(3/2) / sqrt(J)  =>  V = (S sqrt(J) / 2)^(2/3) */
        *req_v = scurve_pow23(S * sqrt(maxJ) / 2.0);
        return 1;
    }
    /* S = V^2/A + V A/J  =>  V^2 + k V - A S = 0 */
    double disc = k * k + 4.0 * maxA * S;
    if (disc < 0.0) {
        *req_v = 0.0;
        return -1;
    }
    *req_v = 0.5 * (-k + sqrt(disc));
    return 1;
}

/* Invert triangular s = (Vs + Ve) sqrt((Vs-Ve)/J) for Vs >= Ve. */
static double scurve_max_start_triangular(double S, double Ve, double maxJ) {
    double JS2 = maxJ * S * S;
    double u;
    int i;

    if (Ve <= TP_VEL_EPSILON) {
        return scurve_pow23(S * sqrt(maxJ));
    }

    /* Small-u guess: 4 Ve^2 u ~ J S^2 */
    u = JS2 / (4.0 * Ve * Ve);
    if (u < 0.0) {
        u = 0.0;
    }

    for (i = 0; i < 20; ++i) {
        double a = u + 2.0 * Ve;
        double f = u * a * a - JS2;
        double fp = a * (3.0 * u + 2.0 * Ve);
        double un;
        if (fabs(fp) < 1e-18) {
            break;
        }
        un = u - f / fp;
        if (un < 0.0) {
            un = 0.5 * u;
        }
        if (fabs(un - u) <= 1e-12 * fmax(1.0, un)) {
            u = un;
            break;
        }
        u = un;
    }
    return Ve + u;
}

int findSCurveVSpeed(double distence, double maxA, double maxJ, double* req_v){
    if (!req_v) {
        return -1;
    }
    if (distence <= 0 || maxA <= 0 || maxJ <= 0) {
        *req_v = 0.0;
        return -1;
    }
    return scurve_vpeak_rest_to_rest(distence, maxA, maxJ, req_v);
}

int findSCurveVSpeedWithEndSpeed(double distance, double Ve,
                                  double maxA, double maxJ, double* req_v) {
    double d_min, lo, hi, mid;
    int i;

    if (!req_v) {
        return -1;
    }
    if (distance <= 0 || maxA <= 0 || maxJ <= 0) {
        *req_v = fabs(Ve);
        return -1;
    }
    Ve = fabs(Ve);
    if (Ve <= TP_VEL_EPSILON) {
        return findSCurveVSpeed(distance, maxA, maxJ, req_v);
    }

    d_min = scurve_dist_speed_change(0.0, Ve, maxA, maxJ);
    if (distance <= d_min) {
        /* Not enough room to reach Ve; report the rest-to-rest peak. */
        return findSCurveVSpeed(distance, maxA, maxJ, req_v);
    }

    /* Extra length: min-time goes above Ve then down. Peak solves
     * dist(0, Vp) + dist(Vp, Ve) = distance, Vp >= Ve. */
    /* Ending at Ve > 0 needs less braking than rest-to-rest, so the peak
     * can exceed the 0→0 peak. Infinite-jerk (Vs^2 = Ve^2 + 2 A S) is a
     * safe upper bound. */
    lo = Ve;
    hi = sqrt(Ve * Ve + 2.0 * maxA * distance);
    if (hi < Ve) {
        hi = Ve;
    }
    for (i = 0; i < 40; ++i) {
        double s;
        mid = 0.5 * (lo + hi);
        s = scurve_dist_speed_change(0.0, mid, maxA, maxJ)
            + scurve_dist_speed_change(mid, Ve, maxA, maxJ);
        if (s > distance) {
            hi = mid;
        } else {
            lo = mid;
        }
    }
    *req_v = 0.5 * (lo + hi);
    return 1;
}

int findSCurveMaxStartSpeed(double distance, double Ve,
                            double maxA, double maxJ, double* req_v) {
    double k, disc, Vs;

    if (!req_v) {
        return -1;
    }
    if (distance <= 0 || maxA <= 0 || maxJ <= 0) {
        *req_v = fabs(Ve);
        return -1;
    }

    Ve = fabs(Ve);

    k = scurve_k(maxA, maxJ);
    /* Trapezoidal-accel invert of
     *   S = (Vs^2 - Ve^2)/(2A) + (Vs - Ve) A/(2J)
     *   Vs^2 + k Vs - (2 A S + Ve^2 + k Ve) = 0
     */
    disc = k * k + 4.0 * (2.0 * maxA * distance + Ve * Ve + k * Ve);
    if (disc < 0.0) {
        *req_v = Ve;
        return 1;
    }
    Vs = 0.5 * (-k + sqrt(disc));
    if (Vs < Ve) {
        Vs = Ve;
    }

    if (Vs - Ve + 1e-12 >= k) {
        *req_v = Vs;
        return 1;
    }

    /* Δv too small to reach A — triangular invert. */
    *req_v = scurve_max_start_triangular(distance, Ve, maxJ);
    if (*req_v < Ve) {
        *req_v = Ve;
    }
    return 1;
}

double calcDecelerateTimes(double v, double amax, double jerk, double* t1, double* t2){
    v = fabs(v);

    if (v < TP_VEL_EPSILON) {
        if (t1 != NULL) *t1 = 0.0;
        if (t2 != NULL) *t2 = 0.0;
        return 0.0;
    }

    if (amax <= 0.0 || jerk <= 0.0) {
        if (t1 != NULL) *t1 = 0.0;
        if (t2 != NULL) *t2 = 0.0;
        return 0.0;
    }

    double T1 = amax / jerk;
    double v_loss_jerk_phases = amax * amax / jerk;
    double T2 = 0.0;

    if (v >= v_loss_jerk_phases) {
        T2 = (v - v_loss_jerk_phases) / amax;
        if (T2 < 0.0) {
            T2 = 0.0;
        }
    } else {
        T1 = sqrt(v / jerk);
        T2 = 0.0;
    }

    if (t1 != NULL) *t1 = T1;
    if (t2 != NULL) *t2 = T2;
    return T1 * 2.0 + T2;
}

double calcSCurveSpeedWithT(double amax, double jerk, double T) {
    double T1;

    if (amax <= 0.0 || jerk <= 0.0 || T <= 0.0) {
        return 0.0;
    }

    /* Speed from rest after time T if we only try to speed up (do not
     * flatten acceleration back to 0). Matches the trapezoidal analogue
     * v = A T, minus the jerk-ramp tax.
     *
     *   T <= A/J : still in the jerk ramp, v = (1/2) J T^2
     *   T >  A/J : v = A T - A^2 / (2 J)
     */
    T1 = amax / jerk;
    if (T <= T1) {
        return 0.5 * jerk * T * T;
    }
    return amax * T - 0.5 * amax * amax / jerk;
}

/* ================================================================
 * Legacy functions kept for simple_tp.c compatibility
 * ================================================================ */

/* PT = P0 + V0 * T + 0.5 * A0 * T^2 + J * T^3 / 6
 * VT = V0 + A0 * T + J * T^2 / 2
 * AT = A0 + J * T
 */

double nextAccel(double t, double targetV, double v, double a, double maxA,
                        double maxJ) {
  double max_da, tiny_da, vel_err, acc_req;
  max_da = delta_accel(t, maxJ);
  tiny_da = max_da * t * 0.001;
  vel_err = targetV - v;
  if (vel_err > tiny_da){
    acc_req = -max_da +
              sqrt(2.0 * maxJ * vel_err + max_da * max_da);
  }else if (vel_err < -tiny_da){
    acc_req = max_da -
              sqrt(-2.0 * maxJ * vel_err + max_da * max_da);
  }else{
    acc_req = 0.0;
  }
  if (acc_req > maxA){
    acc_req = maxA;
  }else if (acc_req < -maxA){
    acc_req = -maxA;
  }
  if (acc_req > a + max_da){
    return a + max_da;
  }else if (acc_req < a - max_da){
    return a - max_da;
  }else{
    return acc_req;
  }
}

double nextSpeed(double v, double a, double t, double targetV, double maxA, double maxJ, double* req_v, double* req_a, double* req_j) {
  double v0 = v;
  double a0 = a;
  double nextA;
  double max_da;
  double v_next;

  if (t <= 0.0 || maxA <= 0.0 || maxJ <= 0.0) {
    if (req_v) *req_v = v;
    if (req_a) *req_a = a;
    if (req_j) *req_j = 0.0;
    return v;
  }

  nextA = nextAccel(t, targetV, v0, a0, maxA, maxJ);

  /* Exact-landing acceleration if this step would cross targetV. */
  {
    double deltaV = (a0 + nextA) * t / 2.0;
    if ((deltaV < 0.0 && targetV < v0 && v0 + deltaV < targetV) ||
        (0.0 < deltaV && v0 < targetV && targetV < v0 + deltaV)) {
      nextA = 2.0 * (targetV - v0) / t - a0;
    }
  }

  if (nextA > maxA) {
    nextA = maxA;
  } else if (nextA < -maxA) {
    nextA = -maxA;
  }

  max_da = maxJ * t;
  if (nextA > a0 + max_da) {
    nextA = a0 + max_da;
  } else if (nextA < a0 - max_da) {
    nextA = a0 - max_da;
  }

  /* Integrate the limited step. Do not replace v with Δv. */
  v_next = v0 + (a0 + nextA) * t / 2.0;

  /* If we still crossed the target after clamps, land on it and back-solve a
   * consistent nextA (then re-clamp jerk; velocity stays at target). */
  if ((v0 < targetV && v_next > targetV) || (v0 > targetV && v_next < targetV)) {
    v_next = targetV;
    nextA = 2.0 * (targetV - v0) / t - a0;
    if (nextA > maxA) nextA = maxA;
    else if (nextA < -maxA) nextA = -maxA;
    if (nextA > a0 + max_da) nextA = a0 + max_da;
    else if (nextA < a0 - max_da) nextA = a0 - max_da;
    v_next = v0 + (a0 + nextA) * t / 2.0;
  }

  if (req_j) *req_j = (nextA - a0) / t;
  if (req_a) *req_a = nextA;
  if (req_v) *req_v = v_next;
  return v_next;
}

double stoppingDist(double v, double a, double maxA, double maxJ) {
    double d = 0.0;
    double peak;
    double deltaV;

    if (maxA <= 0.0 || maxJ <= 0.0) {
        return 0.0;
    }
    if (fabs(v) < TP_VEL_EPSILON && a <= 0.0) {
        return 0.0;
    }
    if (v < 0.0) {
        v = -v;
        a = -a;
    }

    /* Still accelerating: jerk down to a = 0 first. */
    if (a > 0.0) {
        double t = a / maxJ;
        d += sc_distance(t, v, a, -maxJ);
        v += delta_velocity(t, a, -maxJ);
        a = 0.0;
        if (v <= TP_VEL_EPSILON) {
            return fmax(d, 0.0);
        }
    }

    /* No-plateau peak deceleration from current (v, a). */
    peak = -sqrt(v * maxJ + 0.5 * a * a);
    if (peak < -maxA) {
        peak = -maxA;
    }

    if (a < peak) {
        /* Already more negative than the peak we need: jerk toward 0 until v = 0.
         * v + a t + (1/2) J t^2 = 0  =>  t = (-a - sqrt(a^2 - 2 J v)) / J  */
        double disc = a * a - 2.0 * maxJ * v;
        double t;
        if (disc < 0.0) {
            disc = 0.0;
        }
        t = (-a - sqrt(disc)) / maxJ;
        if (t < 0.0) {
            t = 0.0;
        }
        d += sc_distance(t, v, a, maxJ);
        return fmax(d, 0.0);
    }

    if (peak < a) {
        double t = (a - peak) / maxJ;
        d += sc_distance(t, v, a, -maxJ);
        v += delta_velocity(t, a, -maxJ);
        a = peak;
        if (v <= TP_VEL_EPSILON) {
            return fmax(d, 0.0);
        }
    }

    if (fabs(a) < 1e-12) {
        return fmax(d, 0.0);
    }

    deltaV = 0.5 * a * a / maxJ;
    if (deltaV < v) {
        double t = (v - deltaV) / -a;
        d += sc_distance(t, v, a, 0);
        v += delta_velocity(t, a, 0);
    }

    d += sc_distance(-a / maxJ, v, a, maxJ);
    return fmax(d, 0.0);
}

double sc_distance(double t, double v, double a, double j) {
  return t * (v + t * (0.5 * a + 1.0 / 6.0 * j * t));
}

double delta_velocity(double t, double a, double j) {
  return t * (a + 0.5 * j * t);
}

double delta_accel(double t, double j) {return j * t;}
