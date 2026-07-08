# A6-EC servo tuning (LinuxCNC / lcec)

Conservative drive loop settings pushed over EtherCAT SDO at startup, plus HAL feedback compensation so the **Logging** tab and `joint.N.f-error` reflect physical tracking error instead of pipeline lag.

Based on the [kalico sota-motion](https://github.com/dderg/kalico/tree/sota-motion) approach (SDO object dictionary instead of StepperOnline GUI). This branch builds on **`cursor/signal-logging-framework-0633`**.

---

## What changes on boot

### Drive SDOs (`ethercat-conf.xml`)

Written once per slave when lcec claims the bus (RAM only — not EEPROM unless you explicitly store parameters).

| SDO | Panel param | Value | Meaning |
|-----|-------------|-------|---------|
| `0x2000.0x05` | C00.04 | 0 | Manual gain mode (disable auto/stiffness table) |
| `0x2000.0x07` | C00.06 | 100 | Load inertia ratio 100% — adjust after measurement |
| `0x2001.0x01` | C01.00 | 300 | Position loop gain **30.0 rad/s** (0.1 rad/s units) |
| `0x2001.0x02` | C01.01 | 200 | Speed loop gain **20.0 Hz** (0.1 Hz units) — primary noise lever |
| `0x2001.0x03` | C01.02 | 3184 | Speed integral **31.84 ms** (0.01 ms units) |
| `0x2001.0x31` | C01.30 | 1 | Adaptive notch filter (1st notch auto) |

Existing CiA limits from signal logging (unchanged):

| SDO | Meaning | XYZ | A |
|-----|---------|-----|---|
| `6065h` | Max position deviation (counts) | 1311 ≈ 0.1 mm | 36 ≈ 0.1° |
| `6066h` | Fault persistence (ms) | 100 | 100 |

**Not configured here:** carrier frequency, velocity/torque feedforward (60B1/60B2), kalico-style system ID — see prior discussion for Tier 2+.

### HAL feedback compensation (`servo_tuning.hal`)

At 1 kHz servo with ~2 ms EtherCAT feedback latency, raw encoder position lags commanded motion. LinuxCNC following error (`cmd − fb`) then includes that blind spot.

```
ghost_lag = joint.N.vel-cmd × ferr-lag-sec     (default 0.002 s)
motor-pos-fb = raw_fb + ghost_lag
```

`joint.N.f-error` and the Logging tab **FERR** channels use the compensated feedback.

**Diagnostic pins** (also logged):

| Pin | Meaning |
|-----|---------|
| `x-ferr-raw` … `a-ferr-raw` | Following error vs **uncompensated** feedback (lag-inflated) |
| `x-ghost-lag` … `a-ghost-lag` | Compensation term (mm or deg) |
| `ferr-lag-sec` | Delay constant — `halcmd setp ferr-lag-sec.value 0.002` |

Disable compensation: `halcmd setp ferr-lag-sec.value 0` or remove `servo_tuning.hal` from `ethercat_mill.ini`.

---

## Tuning workflow (with Logging tab)

1. Start LinuxCNC; confirm no HAL errors.
2. Open **Logging** → select **FERR** → **LOG NEXT PROGRAM** or **START LIVE**.
3. Run `nc_files/x_tuning.ngc` (or jog) and compare:
   - `joint.*.f-error` — compensated (physical estimate)
   - `x-ferr-raw` etc. — raw (shows pipeline lag)
4. If ringing/whine persists, soften **C01.01** first (e.g. `C8 00` → `B0 00` for 17.6 Hz):

   ```bash
   # Example live write (replace 0 with slave index); reverts on power cycle unless stored
   sudo ethercat download -p 0 0x2001 0x02 0x00B0 --type uint16
   ```

5. Re-run the same move; use CSV in `logs/signals/` to compare peak FERR and torque.

### Suggested gain ladder (C01.01 speed gain, u16 hex)

| Step | Hz | SDO `0x2001.0x02` | Notes |
|------|-----|-------------------|-------|
| Current | 20.0 | `C8 00` | Starting point in XML |
| Softer | 17.6 | `B0 00` | −12% |
| Softer | 15.0 | `96 00` | −25% |
| Factory-ish | 25.0 | `FA 00` | kalico cal default |

After changing C01.01, revisit C01.00 / C01.02 if response feels mushy or overshoots.

### Inertia ratio (C00.06)

Default 100% in XML. If accelerations ring but cruise is fine, try 70–130% using vendor software or SDO `0x2000.0x07` and re-log.

---

## Read back parameters

```bash
ethercat slaves -v
sudo ethercat upload -p 0 0x2001 0x02   # speed gain
sudo ethercat upload -p 0 0x2000 0x07   # inertia ratio
```

---

## Files

| Path | Role |
|------|------|
| `ethercat-conf.xml` | SDO tuning + PDO telemetry + 6065/6066 |
| `servo_tuning.hal` | Pipeline-delay compensation |
| `config/logging/signals.json` | FERR raw + ghost lag channels |
| `SIGNAL_LOGGING.md` | Logging tab + HAL telemetry |
| `nc_files/x_tuning.ngc` | Bench excitation program |

---

## Branch

`cursor/a6-tuning-ferror-comp-70f6` — extends `cursor/signal-logging-framework-0633`.
