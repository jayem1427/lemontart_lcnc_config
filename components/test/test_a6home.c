/* Bench test for a6home's state machine (no LinuxCNC, no hardware).
 *
 * Simulates, once per 1 ms servo cycle and in the real thread order:
 *   lcec read -> a6home.read-all -> motion -> cia402.write -> a6home.write-all
 *   -> lcec write -> drive
 *
 * Motion model, from LinuxCNC homing.c / control.c (2.9 and tpnext):
 *  - index-only homing: INDEX_ONLY_START shifts the internal position to
 *    HOME_OFFSET, sets index-enable, creeps at HOME_LATCH_VEL; when
 *    index-enable is cleared, SET_INDEX_POSITION sets motor_offset =
 *    -HOME_OFFSET and pos_cmd = pos_fb, then a final move to HOME.
 *  - the homing state machine (and so HOME_ABORT, which releases
 *    index-enable) only runs in FREE mode, i.e. enabled.
 *  - a joint amp fault drops enable and refuses enable while it is true.
 *  - while disabled, pos_cmd = pos_fb.
 *  - index-enable pin write: 2.9 writes H.index_enable every cycle; tpnext
 *    writes only on its own edges. Both are tested.
 *  - a simulated operator turns the machine back on after a disable, once
 *    nothing refuses it, then jogs 1 mm to prove the joint is usable.
 *
 * Drive model: mode-change lag, homes to a hard stop then to a Z pulse and
 * sets its position to 607C = 0, can start with stale "homed" bits, drops
 * homing on bit 4 low, trips Er87.1 on a CSP target step > MAX_STEP from its
 * reference (= actual position when entering CSP).
 *
 * Run: sh components/test/test_a6home.sh
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

#include "a6home_logic.inc"   /* extracted from a6home.comp by the .sh */

#define DT        0.001
#define MAX_STEP  2.0          /* mm per cycle before the drive trips "Er87.1" */

static int g_naive_cmd = 0;   /* control: pass LinuxCNC's command straight through */

/* ---------------- drive model ---------------- */
typedef struct {
    double pos;
    int mode_req, mode, mode_lag, lagcnt;
    unsigned cw, cw_prev;
    double ref; int in_csp;
    int fault, er87, enabled;
    int hm_active, hm_phase, hm_done, hm_err, stale, stale_cycles;
    double stop_pos, z_clear, v_search;
    long t, fault_at, bit13_at, fault_clear_at;
    int never_ack;
} drive_t;

static unsigned drive_sw(drive_t *d) {
    unsigned sw = (1u << 9);
    if (d->fault) return sw | 0x0008;
    sw |= d->enabled ? 0x0027 : 0x0040;            /* op enabled / switch-on disabled */
    if (d->mode == 8) sw |= (1u << 10);            /* A6: bit 10 always 1 in CSP */
    if (d->mode == 6) {
        if (d->hm_err) sw |= (1u << 10) | (1u << 13);
        else if (d->hm_done || (d->stale && d->stale_cycles > 0)) sw |= (1u << 10) | (1u << 12) | (1u << 15);
        else if (!d->hm_active) sw |= (1u << 10);
    }
    return sw;
}

static void drive_step(drive_t *d, double target, int enable) {
    d->t++;
    if (d->t == d->fault_at) d->fault = 1;
    if (d->fault && d->fault_clear_at && d->t >= d->fault_clear_at && !d->er87) d->fault = 0;
    if (!(d->never_ack && d->mode_req == 6)) {
        if (d->mode_req != d->mode) { if (++d->lagcnt >= d->mode_lag) { d->mode = d->mode_req; d->lagcnt = 0; } }
        else d->lagcnt = 0;
    }
    d->enabled = enable && !d->fault;
    if (!d->enabled) { d->in_csp = 0; d->hm_active = 0; d->cw_prev = d->cw; return; }
    if (d->mode == 8) {
        if (!d->in_csp) { d->ref = d->pos; d->in_csp = 1; }
        if (fabs(target - d->ref) > MAX_STEP) { d->fault = 1; d->er87 = 1; d->enabled = 0; }
        else { d->pos = target; d->ref = target; }
    } else if (d->mode == 6) {
        d->in_csp = 0;
        int b4 = (d->cw >> 4) & 1, b4p = (d->cw_prev >> 4) & 1;
        if (b4 && !b4p) { d->hm_active = 1; d->hm_phase = 0; d->hm_done = 0; d->hm_err = 0; }
        if (!b4) d->hm_active = 0;
        if (d->hm_active && !d->hm_done && !d->hm_err) {
            if (d->stale_cycles > 0) d->stale_cycles--;
            if (d->t == d->bit13_at) d->hm_err = 1;
            else if (d->hm_phase == 0) { d->pos -= d->v_search * DT; if (d->pos <= d->stop_pos) { d->pos = d->stop_pos; d->hm_phase = 1; } }
            else if (d->hm_phase == 1) { d->pos += 1.0 * DT; if (d->pos >= d->stop_pos + d->z_clear) { d->pos = 0.0; d->hm_done = 1; d->stale = 0; } }
        }
    }
    d->cw_prev = d->cw;
}

/* ---------------- motion model ---------------- */
enum { H_IDLE, H_WAIT_INDEX, H_FINAL, H_ABORT };
typedef struct {
    double pos_cmd, pos_fb, motor_offset, motor_pos_cmd;
    int enabled, homing, homed, hstate, H_ie, H_ie_prev, pin_ie;
    double home_offset, home, latch_vel, final_vel;
    int style29;
} motion_t;

static void motion_cycle(motion_t *m, double motor_pos_fb, int amp_fault, int want_home, int esc) {
    m->H_ie = m->pin_ie;                                  /* read_homing_in_pins */
    m->pos_fb = motor_pos_fb - m->motor_offset;           /* process_inputs */
    if (amp_fault && m->enabled) {                        /* check_for_faults + disable */
        m->enabled = 0;
        if (m->homing) m->hstate = H_ABORT;               /* do_cancel_homing */
    }
    if (esc && m->homing) m->hstate = H_ABORT;
    if (m->enabled) {                                     /* do_homing only in FREE */
        if (want_home && !m->homing) {                    /* INDEX_ONLY_START */
            m->homing = 1; m->homed = 0;
            double off = m->home_offset - m->pos_fb;
            m->pos_cmd += off; m->pos_fb += off; m->motor_offset -= off;
            m->H_ie = 1; m->hstate = H_WAIT_INDEX;
        }
        if (m->hstate == H_ABORT) { m->homing = 0; m->homed = 0; m->H_ie = 0; m->hstate = H_IDLE; }
        else if (m->hstate == H_WAIT_INDEX) {
            if (!m->H_ie) {                               /* SET_INDEX_POSITION */
                m->motor_offset = -m->home_offset;
                m->pos_fb = motor_pos_fb - m->motor_offset;
                m->pos_cmd = m->pos_fb;
                m->hstate = H_FINAL;
            } else m->pos_cmd += m->latch_vel * DT;
        }
        if (m->hstate == H_FINAL) {
            double d = m->home - m->pos_cmd, s = m->final_vel * DT;
            if (fabs(d) <= s) { m->pos_cmd = m->home; m->homing = 0; m->homed = 1; m->hstate = H_IDLE; }
            else m->pos_cmd += (d > 0 ? s : -s);
        }
    } else {
        m->pos_cmd = m->pos_fb;                           /* EMCMOT_MOTION_DISABLED */
    }
    m->motor_pos_cmd = m->pos_cmd + m->motor_offset;      /* output_to_hal */
    if (m->style29) m->pin_ie = m->H_ie;                  /* write_homing_out_pins */
    else {
        if (m->H_ie && !m->H_ie_prev) m->pin_ie = 1;
        else if (!m->H_ie && m->H_ie_prev) m->pin_ie = 0;
    }
    m->H_ie_prev = m->H_ie;
}

/* ---------------- scenarios ---------------- */
typedef struct {
    const char *name;
    int stale, never_ack, rehome, expect_homed, expect_er87;
    long fault_at, fault_clear_after, bit13_at, esc_at, estop_at;
} scen_t;

static int run(const scen_t *sc, int style29) {
    drive_t d; memset(&d, 0, sizeof d);
    d.pos = 87.3; d.mode = 8; d.mode_req = 8; d.mode_lag = 3; d.enabled = 1;
    d.stop_pos = 60.0; d.z_clear = 4.7; d.v_search = 20.0;
    d.stale = sc->stale; d.stale_cycles = sc->stale ? 5 : 0;
    d.fault_at = sc->fault_at; d.bit13_at = sc->bit13_at; d.never_ack = sc->never_ack;
    d.fault_clear_at = sc->fault_at && sc->fault_clear_after ? sc->fault_at + sc->fault_clear_after : 0;

    motion_t m; memset(&m, 0, sizeof m);
    m.enabled = 1; m.home_offset = -2.5; m.home = 5.0; m.latch_vel = -0.01; m.final_vel = 3.33;
    m.pos_cmd = d.pos; m.motor_pos_cmd = d.pos; m.style29 = style29;

    int st = 0, busy = 0, why = 0, hg = 0, hd = 0, er = 0;
    double tm = 0, max_step = 0, prev_cd = NAN;
    int homes_done = 0, homes_wanted = sc->rehome ? 2 : 1, any_amp = 0, last_amp = 0;
    long disabled_for = 0, home_at = 100, jog_at = -1, deadlock = 0;
    double jog_target = NAN;
    int phase = 0;  /* 0 homing, 1 recovered/settling, 2 jog check */

    for (long cyc = 1; cyc < 400000; cyc++) {
        unsigned sw = drive_sw(&d); int opd = d.mode; double fb = d.pos;
        int ie_o, flt; double fbj;
        a6h_read(&st, &tm, &busy, &why, sw, opd, m.pin_ie, d.fault, m.enabled, fb, m.motor_pos_cmd, DT,
                 40.0, 1.0, 8, &ie_o, &fbj, &flt, &hg, &hd, &er);
        m.pin_ie = ie_o; any_amp |= flt; last_amp = flt;

        int want_home = (cyc == home_at);
        if (sc->estop_at && cyc == sc->estop_at && m.homing) { m.enabled = 0; m.hstate = H_ABORT; }
        int was_homing = m.homing;
        motion_cycle(&m, fbj, flt, want_home, sc->esc_at && cyc == sc->esc_at);
        if (was_homing && !m.homing && m.homed) { homes_done++; if (homes_done < homes_wanted) { home_at = cyc + 500; d.stale = 1; d.stale_cycles = 5; } }

        /* operator: turn the machine back on 300 cycles after a disable, once nothing refuses it */
        if (!m.enabled) { disabled_for++; if (disabled_for > 300 && !flt) { m.enabled = 1; m.pos_cmd = m.pos_fb; disabled_for = 0; } if (disabled_for > 50000) { deadlock = 1; break; } }

        /* after homing done or recovery: jog +1 mm and check the drive follows */
        if (phase == 0 && m.enabled && !m.homing && cyc > home_at + 10 && st == 0 && (homes_done >= homes_wanted || !sc->expect_homed)) { phase = 1; jog_at = cyc + 200; }
        if (phase == 1 && cyc == jog_at) { jog_target = m.pos_cmd + 1.0; phase = 2; }
        if (phase == 2 && m.enabled) { double dd = jog_target - m.pos_cmd; double s = 5.0 * DT; m.pos_cmd += fabs(dd) <= s ? dd : (dd > 0 ? s : -s); m.motor_pos_cmd = m.pos_cmd + m.motor_offset; }

        unsigned cwo; int mo; double cd;
        a6h_write(st, 0x0F, opd, 8, fb, m.motor_pos_cmd, &cwo, &mo, &cd);
        if (g_naive_cmd) cd = m.motor_pos_cmd;
        if (d.mode == 8 && d.in_csp && !isnan(prev_cd)) { double j = fabs(cd - prev_cd); if (j > max_step) max_step = j; }
        prev_cd = cd;
        d.cw = cwo; d.mode_req = mo;
        drive_step(&d, cd, m.enabled);
        if (phase == 2 && cyc > jog_at + 600) break;
        if (d.er87 && cyc > 20000) break;
    }

    int ok = 1; char w[200] = "";
#define FAIL(...) do { if (ok) snprintf(w, sizeof w, __VA_ARGS__); ok = 0; } while (0)
    if (d.er87 != sc->expect_er87) FAIL("Er87.1=%d expected %d (max CSP step %.4f mm)", d.er87, sc->expect_er87, max_step);
    if (!sc->expect_er87) {
        if (deadlock) FAIL("DEADLOCK: machine could not be re-enabled (amp-fault stuck, a6home state %d)", st);
        if (m.homed != sc->expect_homed) FAIL("homed=%d expected %d", m.homed, sc->expect_homed);
        if (phase != 2) FAIL("never recovered to a usable joint (a6home state %d, enabled %d, ie %d)", st, m.enabled, m.pin_ie);
        else if (fabs((jog_target + m.motor_offset) - d.pos) > 1e-6) FAIL("jog after recovery: drive %.6f, expected %.6f", d.pos, jog_target + m.motor_offset);
        if (m.pin_ie) FAIL("index-enable left set");
        if (st != 0) FAIL("a6home not idle (state %d)", st);
        if (last_amp) FAIL("amp-fault still asserted");
        if (max_step > 0.01) FAIL("CSP target step %.4f mm", max_step);
        if (sc->expect_homed) {
            if (any_amp) FAIL("amp fault during a good home");
            if (homes_done != homes_wanted) FAIL("homes %d/%d", homes_done, homes_wanted);
        }
    }
    printf("  %-36s %s %s\n", sc->name, ok ? "PASS" : "FAIL", w);
    return ok;
}

int main(void) {
    scen_t s[] = {
        /* name                            stale noack rehome homed er87  fault_at clr   bit13 esc   estop */
        { "normal hard-stop + Z",            0,   0,    0,    1,    0,     0,     0,    0,    0,    0 },
        { "stale homed bits at start",       1,   0,    0,    1,    0,     0,     0,    0,    0,    0 },
        { "home twice, stale bits again",    1,   0,    1,    1,    0,     0,     0,    0,    0,    0 },
        { "drive fault during homing",       0,   0,    0,    0,    0,  1500,   400,    0,    0,    0 },
        { "homing error (bit 13)",           0,   0,    0,    0,    0,     0,     0, 1200,    0,    0 },
        { "drive never acks mode 6",         0,   1,    0,    0,    0,     0,     0,    0,    0,    0 },
        { "ESC abort, machine stays on",     0,   0,    0,    0,    0,     0,     0,    0, 1000,    0 },
        { "E-stop / machine off mid-homing", 0,   0,    0,    0,    0,     0,     0,    0,    0,  900 },
    };
    int n = sizeof s / sizeof s[0], pass = 0, total = 0;
    for (int style = 0; style < 2; style++) {
        printf("index-enable written %s:\n", style ? "every cycle (LinuxCNC 2.9)" : "on edges (tpnext)");
        for (int i = 0; i < n; i++) { pass += run(&s[i], style); total++; }
    }
    g_naive_cmd = 1;
    printf("negative control:\n");
    scen_t ctl = { "naive cmd pass-through -> Er87.1",  0, 0, 0, 0, 1, 0, 0, 0, 0, 0 };
    int ctl_ok = run(&ctl, 0);
    printf("\n%d/%d passed, control %s\n", pass, total, ctl_ok ? "OK" : "FAILED");
    return (pass == total && ctl_ok) ? 0 : 1;
}
