# 33metal / minimonster config review

Someone else's LinuxCNC dump (Probe Basic + Omron G5 + Leadshine L6N).

| Path | Contents |
|------|----------|
| [`DIAGNOSIS.md`](DIAGNOSIS.md) | MPG / cursor / X-axis failure analysis |
| [`original/`](original/) | Files as uploaded |
| [`patched/`](patched/) | Suggested bring-up fixes (soft limits, FERROR, drive 6065, estop net) |

**Still needed from them:** `custom.hal` (referenced by the INI, not in the dump) and any pendant `xhc-*.hal`.
