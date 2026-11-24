/* Bench test for a6home's state machine (no LinuxCNC, no hardware).
 *
 * Simulates, once per 1 ms servo cycle and in the real thread order:
 *   lcec read -> a6home.read -> motion (index-only homing, like homing.c)
 *   -> cia402.write -> a6home.write -> lcec write -> drive
 * The drive model has a mode-change lag, homes to a hard stop then to a Z
 * pulse, sets its position to 607C = 0 when done, can start with stale
 * "homed" status bits, and trips Er87.1 on any CSP target step bigger than
 * MAX_STEP (what A6 users hit after drive homing).
 *
 * Build and run:  sh components/test/test_a6home.sh
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

#include "a6home_logic.inc"   /* extracted from a6home.comp by the .sh */

#define DT        0.001
#define SCALE     13107.2      /* counts/mm */
#define MAX_STEP  2.0          /* mm per cycle before the drive trips "Er87.1" */

static int g_naive_cmd = 0;   /* control: pass LinuxCNC's command straight through */

/* ---------------- drive model ---------------- */
typedef struct {
    double pos;          /* mm, drive frame (0x6064 / SCALE) */
    int mode_req, mode;  /* 0x6060 / 0x6061 */
    int mode_lag;        /* cycles until mode_req becomes mode */
    int lagcnt;
    unsigned cw, cw_prev;
    double last_target; int have_target;
    int fault, er87;
    /* homing */
    int hm_active, hm_phase, hm_done, hm_err;
    int stale_cycles;    /* cycles after start before stale bits clear */
    double stop_pos;     /* mm, where the hard stop is (drive frame) */
    double z_clear;      /* mm from stop to Z pulse */
    double v_search;     /* mm/s */
    int inject_fault_at, inject_bit13_at, never_ack;
    long t;
} drive_t;

static unsigned drive_sw(drive_t *d) {
    unsigned sw = 0x0027 | (1u << 9);        /* op enabled + remote */
    if (d->fault) sw = 0x0008 | (1u << 9);
    if (d->mode == 8) sw |= (1u << 10);      /* A6: bit 10 always 1 in CSP */
    if (d->mode == 6) {
        if (d->hm_done) sw |= (1u << 10) | (1u << 12) | (1u << 15);
        else if (d->hm_err) sw |= (1u << 10) | (1u << 13);
        else if (d->hm_active && d->stale_cycles > 0) sw |= (1u << 10) | (1u << 12) | (1u << 15);
        else if (!d->hm_active) sw |= (1u << 10) | (d->hm_phase == 99 ? (1u << 12) : 0);
    }
    return sw;
}

static void drive_step(drive_t *d, double target_mm) {
    d->t++;
    if (d->t == d->inject_fault_at) d->fault = 1;
    /* mode change with lag */
    if (!d->never_ack || d->mode_req != 6) {
        if (d->mode_req != d->mode) {
            if (++d->lagcnt >= d->mode_lag) { d->mode = d->mode_req; d->lagcnt = 0; }
        } else d->lagcnt = 0;
    }
    if (d->fault) { d->cw_prev = d->cw; return; }
    if (d->mode == 8) {
        if (!d->have_target) d->last_target = d->pos;   /* entering CSP: reference = actual */
        if (fabs(target_mm - d->last_target) > MAX_STEP) { d->fault = 1; d->er87 = 1; }
        else d->pos = target_mm;
        d->last_target = target_mm; d->have_target = 1;
        d->hm_active = 0;
    } else if (d->mode == 6) {
        d->have_target = 0;       /* drive ignores 607A in mode 6 */
        int bit4 = (d->cw >> 4) & 1, bit4p = (d->cw_prev >> 4) & 1;
        if (bit4 && !bit4p) { d->hm_active = 1; d->hm_phase = 0; d->hm_done = 0; d->hm_err = 0; }
        if (!bit4) d->hm_active = 0;
        if (d->hm_active && !d->hm_done && !d->hm_err) {
            if (d->stale_cycles > 0) d->stale_cycles--;
            if (d->t == d->inject_bit13_at) { d->hm_err = 1; }
            else if (d->hm_phase == 0) {                 /* to the hard stop */
                d->pos -= d->v_search * DT;
                if (d->pos <= d->stop_pos) { d->pos = d->stop_pos; d->hm_phase = 1; }
            } else if (d->hm_phase == 1) {               /* back off to Z */
                d->pos += 1.0 * DT;
                if (d->pos >= d->stop_pos + d->z_clear) { d->pos = 0.0; d->hm_done = 1; d->hm_phase = 99; }
            }
        }
    }
    d->cw_prev = d->cw;
}

/* ---------------- motion model (index-only homing, cf. homing.c) ---------------- */
typedef struct {
    double pos_cmd, pos_fb, motor_offset, motor_pos_cmd;
    int enabled, homing, homed, ie, state; /* 0 idle, 1 wait index, 2 final move */
    double home_offset, home, latch_vel, final_vel;
} motion_t;

static void motion_start_home(motion_t *m, double motor_pos_fb) {
    m->homing = 1; m->homed = 0;
    m->pos_fb = motor_pos_fb - m->motor_offset;
    /* HOME_INDEX_ONLY_START: set current position to home_offset (internal only) */
    double off = m->home_offset - m->pos_fb;
    m->pos_cmd += off; m->pos_fb += off; m->motor_offset -= off;
    m->ie = 1; m->state = 1;
}

static void motion_step(motion_t *m, double motor_pos_fb, int amp_fault) {
    m->pos_fb = motor_pos_fb - m->motor_offset;
    if (amp_fault && m->enabled) {          /* motion disables, homing aborts */
        m->enabled = 0;
        if (m->homing) { m->homing = 0; m->homed = 0; m->ie = 0; m->state = 0; }
    }
    if (!m->enabled) { m->pos_cmd = m->pos_fb; }
    else if (m->homing && m->state == 1) {
        if (!m->ie) {                        /* HOME_SET_INDEX_POSITION */
            m->motor_offset = -m->home_offset;
            m->pos_fb = motor_pos_fb - m->motor_offset;
            m->pos_cmd = m->pos_fb;
            m->state = 2;
        } else {
            m->pos_cmd += m->latch_vel * DT;  /* creep */
        }
    }
    if (m->enabled && m->homing && m->state == 2) {
        double d = m->home - m->pos_cmd, s = m->final_vel * DT;
        if (fabs(d) <= s) { m->pos_cmd = m->home; m->homing = 0; m->homed = 1; m->state = 0; }
        else m->pos_cmd += (d > 0 ? s : -s);
    }
    m->motor_pos_cmd = m->pos_cmd + m->motor_offset;
}

/* ---------------- one scenario ---------------- */
typedef struct {
    const char *name;
    int stale, fault_at, bit13_at, never_ack, abort_at, rehome, expect_homed, expect_er87;
} scen_t;

static int run(const scen_t *sc) {
    drive_t d; memset(&d, 0, sizeof d);
    d.pos = 87.3; d.mode = 8; d.mode_req = 8; d.mode_lag = 3;
    d.stop_pos = 60.0; d.z_clear = 4.7; d.v_search = 20.0;
    d.stale_cycles = sc->stale ? 5 : 0; d.hm_phase = sc->stale ? 99 : 0;
    d.inject_fault_at = sc->fault_at; d.inject_bit13_at = sc->bit13_at; d.never_ack = sc->never_ack;

    motion_t m; memset(&m, 0, sizeof m);
    m.enabled = 1; m.home_offset = -2.5; m.home = 5.0; m.latch_vel = -0.01; m.final_vel = 3.33;
    m.motor_offset = 0; m.pos_cmd = d.pos; m.motor_pos_cmd = d.pos;

    int st = 0, busy = 0, why = 0, hg = 0, hd = 0, er = 0;
    double tm = 0;
    double max_jump = 0, prev_target = NAN;
    int homes_done = 0, homes_wanted = sc->rehome ? 2 : 1, started = 0, any_amp = 0, settle = 0;

    for (long cyc = 1; cyc < 60000; cyc++) {
        /* lcec read */
        unsigned sw = drive_sw(&d);
        int opd = d.mode;
        double fb_drive = d.pos;
        /* a6home.read */
        int ie_o, flt; double fbj;
        a6h_read(&st, &tm, &busy, &why, sw, opd, m.ie, d.fault, fb_drive, m.motor_pos_cmd, DT,
                 40.0, 1.0, 8, &ie_o, &fbj, &flt, &hg, &hd, &er);
        m.ie = ie_o;
        any_amp |= flt;
        /* motion */
        if (!started && cyc == 100) { motion_start_home(&m, fbj); started = 1; }
        if (sc->abort_at && cyc == sc->abort_at && m.homing) { m.homing = 0; m.ie = 0; m.state = 0; }
        int was_homing = m.homing;
        motion_step(&m, fbj, flt);
        if (was_homing && !m.homing && m.homed) {
            homes_done++;
            if (homes_done < homes_wanted) { /* home again later */ started = 0; cyc = 0; }
        }
        /* cia402.write: operation enabled */
        unsigned cw_in = 0x0F;
        /* a6home.write */
        unsigned cwo; int mo; double cd;
        a6h_write(st, cw_in, opd, 8, fb_drive, m.motor_pos_cmd, &cwo, &mo, &cd);
        if (g_naive_cmd) cd = m.motor_pos_cmd;
        /* drive */
        d.cw = cwo; d.mode_req = mo;
        if (d.mode == 8 && !isnan(prev_target)) { double j = fabs(cd - prev_target); if (j > max_jump) max_jump = j; }
        prev_target = cd;
        drive_step(&d, cd);
        if (sc->rehome && homes_done == 1 && cyc == 50) { d.stale_cycles = 5; } /* stale bits again */
        if (homes_done >= homes_wanted && st == 0 && cyc > 200 && ++settle > 20) break;
        if (!m.enabled && st == 0 && cyc > 3000) break;
    }

    int ok = 1;
    char why_s[256] = "";
    if (m.homed != sc->expect_homed) { ok = 0; snprintf(why_s, sizeof why_s, "homed=%d expected %d", m.homed, sc->expect_homed); }
    if (d.er87 != sc->expect_er87) { ok = 0; snprintf(why_s, sizeof why_s, "Er87.1=%d expected %d (max CSP step %.4f mm)", d.er87, sc->expect_er87, max_jump); }
    if (sc->expect_homed) {
        if (fabs(m.pos_fb - m.home) > 1e-6) { ok = 0; snprintf(why_s, sizeof why_s, "pos_fb %.6f != HOME", m.pos_fb); }
        /* drive frame: index = 0, so machine HOME is HOME-HOME_OFFSET in drive mm */
        if (fabs(d.pos - (m.home - m.home_offset)) > 1e-6) { ok = 0; snprintf(why_s, sizeof why_s, "drive pos %.6f, expected %.6f", d.pos, m.home - m.home_offset); }
        if (max_jump > 0.01) { ok = 0; snprintf(why_s, sizeof why_s, "CSP target step %.4f mm", max_jump); }
        if (any_amp) { ok = 0; snprintf(why_s, sizeof why_s, "amp fault raised"); }
        if (homes_done != homes_wanted) { ok = 0; snprintf(why_s, sizeof why_s, "homes %d/%d", homes_done, homes_wanted); }
    } else {
        if (m.ie) { ok = 0; snprintf(why_s, sizeof why_s, "index-enable left set"); }
        if (st != 0 && !d.fault) { ok = 0; snprintf(why_s, sizeof why_s, "a6home stuck in state %d", st); }
    }
    printf("%-34s %s %s\n", sc->name, ok ? "PASS" : "FAIL", why_s);
    return ok;
}

int main(void) {
    scen_t s[] = {
        /* name                         stale fault bit13 noack abort rehome homed er87 */
        { "normal hard-stop + Z",          0,   0,    0,    0,    0,    0,    1,    0 },
        { "stale homed bits at start",     1,   0,    0,    0,    0,    0,    1,    0 },
        { "home twice, stale bits again",  1,   0,    0,    0,    0,    1,    1,    0 },
        { "drive fault during homing",     0, 1500,   0,    0,    0,    0,    0,    0 },
        { "homing error (bit 13)",         0,   0, 1200,    0,    0,    0,    0,    0 },
        { "drive never acks mode 6",       0,   0,    0,    1,    0,    0,    0,    0 },
        { "LinuxCNC abort mid-homing",     0,   0,    0,    0, 1000,    0,    0,    0 },
    };
    int n = sizeof s / sizeof s[0], pass = 0;
    for (int i = 0; i < n; i++) pass += run(&s[i]);

    /* negative control: without a6home's command substitution the simulated
     * A6 must trip Er87.1 (proves the harness catches the failure) */
    g_naive_cmd = 1;
    scen_t ctl = { "CONTROL naive cmd -> Er87.1",   0, 0, 0, 0,    0, 0, 0, 1 };
    int ctl_ok = run(&ctl);
    printf("\n%d/%d passed, control %s\n", pass, n, ctl_ok ? "OK" : "FAILED");
    return (pass == n && ctl_ok) ? 0 : 1;
}
