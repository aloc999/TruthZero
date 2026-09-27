# Training recipe — offensive model fine-tune (Pentest-R1 style)

Goal: a security-tuned open model that reasons well inside the ZER0CODE
harness (toolformer behaviour, not closed weights — recipe only).

## Data
1. **Trajectories**: export confirmed swarm campaigns —
   `board.save()` JSON + session SQLite → (state, tool_call, observation)
   triples. Only `VULN_CONFIRMED` paths; drop FP branches.
2. **CVE chains**: `chains/*.yaml` → verify_steps as supervised demos.
3. **Negative mining**: JEV-discarded findings as "do not pursue" examples.

## Stages
1. **SFT**: instruction-tune on (blackboard state → next tool call) pairs.
   Base: Qwen3 / DeepSeek / GLM coding builds with native function calling.
2. **RL (R1-style)**: reward = confirmed finding (1.0) + evidence quality
   (0.3) − FP pursuit (−0.5) − out-of-scope attempt (−1.0, hard).
   Environment = labs (`zer0code lab up crapi|juice|vampi|dvga`) + bench harness.
3. **Guard**: mix in MemoryGuard-blocked lessons as refusal/ignore demos so
   the model treats tool output as data, never instructions.

## Eval
`zer0code bench` (local) → Cybench / AutoPenBench / CVE-Bench when wired.
Ship numbers in ROADMAP before claiming anything.
