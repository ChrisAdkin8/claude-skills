# Spike results: Fixture spec with one spike figure the results don't show

## S1

### How long does one `check-spec.py` run take on this repo's spec?

Expect: under a second.
Runs: 3

#### Commands

```
(cd src && for i in 1 2 3; do /usr/bin/time -p python3 skills/spec/scripts/check-spec.py docs/specs/2026-09-17-spec-spike-phase.md --repo . --read-at ac65fbd > /dev/null; done)
```

#### Output

```
real 0.09
user 0.05
sys 0.02
real 0.08
user 0.05
sys 0.02
real 0.10
user 0.06
sys 0.02
```

#### Verdict

EXPECTED: all three runs finished in under a second.

total_cost_usd: 0.12, num_turns: 5
