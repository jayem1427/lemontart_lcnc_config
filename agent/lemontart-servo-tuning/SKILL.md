---
name: lemontart-servo-tuning
description: Propose one bounded servo gain change from a drive following-error plot and pasted parameters. Use when the operator pastes a Servo Tuning plot, COPY TUNING text, or asks what to change next on this mill. Does not write SDOs or start motion.
---

# Lemontart servo tuning

You advise. The operator applies. Suggestions go into Pending. They press **APPLY TO DRIVE**.

Read `docs/SERVO_TUNING_LLM.md` from the pack root (this file is `skills/lemontart-servo-tuning/SKILL.md`, so the playbook is `../../docs/SERVO_TUNING_LLM.md`). Follow that playbook for shape, step size, and reply format. If you cannot open it, say so and stop.

Read `docs/SERVO_SWAP.md` before you name an object index. The playbook’s C01 labels and the “position ≈ 2× speed” rule are **StepperOnline A6**. A Leadshine EL8-EC uses other indexes, and its torque filter is a time constant in 0.01 ms, not a cutoff in Hz. Do not quote an index that the open manual page does not show. EL7-EC needs its own manual.

- Do not write SDOs, do not start a move, and do not loosen LinuxCNC `FERROR` to hide a tune.
- One small change, or one pair that has to move together.
- If the paste has no gain values, ask for **COPY TUNING**. Do not invent numbers.
- Do not load `config/tuning/presets/` from another machine.
