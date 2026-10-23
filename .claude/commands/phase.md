---
description: Run one phase of the fly_mario_fly redesign with the investigator, implementer, experimenter and reviewer subagents
argument-hint: <phase number 0-7> [optional note]
---

Run phase $ARGUMENTS of docs/REDESIGN_PLAN.md (section 7). You are the coordinator: delegate, do not do the work yourself, and keep your own context small.

1. Read docs/REDESIGN_PLAN.md. State in 3 lines what this phase must deliver and its exit check.
2. If the phase is 0, or the plan marks the topic as an investigation or open decision: use the investigator subagent. Show me its report summary and STOP for my approval.
3. Otherwise:
   a. Use the implementer subagent for this phase only (SPEC first, then code and tests).
   b. Use the experimenter subagent to run the synthetic tests, test scenes and the standard eval once.
   c. Use the reviewer subagent on the diff and the results.
   d. If the reviewer says FIX REQUIRED: send the fix list to the implementer, then re-run only the affected synthetic tests (not the eval unless the model changed), then review again. At most 2 fix rounds - after that stop and ask me.
4. Do not commit. Finish with a short report for me: what was built, the results table (real vs shuffled), the reviewer's verdict, open questions, and the exact git commands to commit if I approve.

Rules for the whole run: the legacy path stays frozen; nothing is tuned on game outcomes; tests stay proportional (CLAUDE.md "Testing"); if any agent is unsure whether something breaks the rule, stop and ask me.
