# 33metal / minimonster config review

Someone else's LinuxCNC dump (Probe Basic + Omron G5 + Leadshine L6N).

| Path | Contents |
|------|----------|
| [`DIAGNOSIS.md`](DIAGNOSIS.md) | MPG / cursor / X-axis failure analysis |
| [`original/`](original/) | Files as uploaded |
| [`patched/`](patched/) | Suggested bring-up fixes (soft limits, FERROR, drive 6065, estop net) |

**`custom.hal` is in** — spindle Modbus only; **no pendant**. If they truly have an XHC, that HALFILE is still missing from the machine.
