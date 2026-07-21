# File connection map

How the important files in this repo wire together. Probe macros under
`probe_basic/subroutines/` are collapsed into groups — there are dozens of
near-identical probe routines that all hang off the same INI path.

![File connection map](assets/file_map.svg)

```mermaid
flowchart TB
  subgraph launch["Launch"]
    DESKTOP["Launch_Mill.desktop"]
    SH["launch.sh"]
  end

  INI["ethercat_mill.ini<br/>main hub"]

  DESKTOP --> SH --> INI

  subgraph hal["HAL stack loaded by INI"]
    LOADUSR["ethercat_loadusr.hal"]
    MILLHAL["ethercat_mill.hal"]
    XHC["xhc-whb04b-6.hal"]
    CUSTOM["custom.hal"]
    POSTGUI["probe_basic/probe_basic_postgui.hal"]
    XML["ethercat-conf.xml"]
    MB2["h100.mb2hal"]
  end

  INI --> LOADUSR --> XML
  INI --> MILLHAL
  INI --> XHC
  INI --> CUSTOM --> MB2
  INI --> POSTGUI

  subgraph ui["Probe Basic UI"]
    YML["probe_basic/custom_config.yml"]
    DIALOG["toolchange_dialog.py<br/>+ toolchange_dialog_pb.ui"]
    TABS["user_tabs/<br/>servo_tuner · signal_monitor · laser_setter"]
    TOOL["probe_basic/tool.tbl"]
    PY["probe_basic/python/"]
  end

  INI --> YML --> DIALOG
  INI --> TABS
  INI --> TOOL
  TABS --> PY

  subgraph gcode["G-code / macros"]
    VAR["linuxcnc.var"]
    SUBS["probe_basic/subroutines/<br/>m600 · tool_touch_off · laser_* · probe_* · on_abort"]
    NC["nc_files/"]
    CPS["linuxcnc-djr.cps"]
  end

  INI --> VAR
  INI --> SUBS
  INI --> NC
  CPS -.->|"emits T… M600"| NC
  NC --> SUBS
```

## Startup chain

| Step | File | Points at |
|------|------|-----------|
| 1 | `Launch_Mill.desktop` / `launch.sh` | `ethercat_mill.ini` |
| 2 | `ethercat_mill.ini` | HAL files, Probe Basic paths, tool table, subroutines, `nc_files/` |
| 3a | `ethercat_loadusr.hal` | `ethercat-conf.xml` (slave chain / SDOs) |
| 3b | `ethercat_mill.hal` | joints, CiA 402, limits, probe mux, laser pin |
| 3c | `xhc-whb04b-6.hal` | pendant → `halui` / jog nets |
| 3d | `custom.hal` | `h100.mb2hal` (VFD) + tune telemetry scales |
| 3e | `probe_basic_postgui.hal` | UI HAL pins after GUI starts |

## UI + Python

```mermaid
flowchart LR
  subgraph tabs["user_tabs"]
    ST["servo_tuner.py"]
    SM["signal_monitor.py"]
    LS["laser_setter.py"]
  end

  subgraph lib["probe_basic/python"]
    AST["a6_servo_tune.py"]
    AAT["a6_auto_tune.py"]
    AGI["a6_graphical_inertia.py"]
    TT["tune_trial.py"]
    RA["resonance_analysis.py"]
    HSL["hal_signal_logger.py"]
    SPW["signal_plot_widget.py"]
    TOP["toplevel.py → remap.py → stdglue.py"]
  end

  subgraph data["config + logs"]
    PRE["config/tuning/presets/X|Y|Z/"]
    INERT["config/tuning/inertia_settings.json"]
    SIG["config/logging/signals.json"]
    LTUNE["logs/tuning/"]
    LSIG["logs/signals/"]
  end

  ST --> AST & AAT & AGI & TT & RA
  SM --> HSL & SPW
  HSL --> AST
  AAT --> AST & RA
  AGI --> AST
  TT --> AST

  AST --> PRE
  AGI --> INERT & LTUNE
  AAT --> PRE & LTUNE
  HSL --> SIG & LSIG
  LS --> VAR2["linuxcnc.var"] & LASER["laser_*.ngc macros"]
```

Helper scripts under `scripts/` are thin CLIs onto the same Python modules:

| Script | Uses |
|--------|------|
| `scripts/run_auto_tune.py` | `a6_auto_tune` + `a6_servo_tune` |
| `scripts/run_signal_logger.py` | `hal_signal_logger` |
| `scripts/plot_signal_log.py` | `config/logging/signals.json` + CSV logs |
| `scripts/visualize_auto_tune_scoring.py` | auto-tune + resonance + demo CSVs |
| `scripts/ui_smoke_servo_tuner_inertia.py` | `servo_tuner` layout smoke test |

## Tool-change path

```mermaid
flowchart LR
  CAM["Fusion post<br/>linuxcnc-djr.cps"] -->|"T n M600"| PROG["nc_files/…"]
  PROG --> INI2["INI REMAP M600"]
  INI2 --> M600["m600.ngc"]
  M600 --> TTO["tool_touch_off.ngc"]
  TTO --> DIALOG2["toolchange_dialog"]
  TTO --> TBL["tool.tbl"]
  TTO --> HAL["ethercat_mill.hal<br/>probe mux"]
```

## What is *not* wired in

- `docs/` — documentation only (this file included)
- `Sigma II Parameter Calculator Rev 2.42.xls`, `h100 manual.pdf` — reference manuals
- Stock Probe Basic probe `*.ngc` macros — all reached only via `SUBROUTINE_PATH`
