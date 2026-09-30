# Record: Install the skills from the Claude Code plugin marketplace, part 2: cutover

What happened to [2026-09-29-plugin-marketplace-2-cutover](../2026-09-29-plugin-marketplace-2-cutover.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan. Sections appear as they're needed, in this order; leave out any that have nothing in them yet.

This spec is part 2 of 2, split on 2026-09-29 from [2026-09-29-plugin-marketplace](../2026-09-29-plugin-marketplace.md), which was verified in three rounds and given a full cold review and one delta review as a single document. That history is in [its record] and covers this part's text as it stood before the split; the split only regrouped that text into two parts, adding each part's Goal, the "Both layouts" Decision bullet in part 1 and the Prerequisite line in part 2, and correcting cross-references. No claim was changed. This part has no saved cold review of its own.

## Verification

- 2026-09-29: spec-verifier, 20 of 27 claims confirmed. Plan holds: yes.
  - Fixed: the 23-file count carries its `-l` derivation; the plugin-name claim now says part 1's W1 names the plugin; "plugins can't ship permission or sandbox settings" is marked *(unverified)*; W3's Done when says the versioned cache path is untested; `docs/containment.md` in W5 says why it is listed; W4's Effort dependency says "and so part 1".
  - Not applied, and why: `CLAUDE.md:32-33` (the rule's bullet starts at line 33, so `:33` is right) and `skills/spec/SKILL.md:6-10` (the `allowed-tools` value ends at line 9; line 10 is the closing `---`).
  - Not checked by the verifier, and checked here: "draft PR #27, open" (`gh pr view 27` on 2026-09-29: open, draft).
- Changed after the verifier on 2026-09-30: W3's Done when for `check-spec.py` over `docs/specs/` now says every spec that passed before still passes, since two older specs fail for missing notes in `~/notes`, from part 1's delta review row 4.
- Marked reviewed on 2026-09-30 by the user's decision, with no cold review of its own: its text was covered by the full and delta reviews of the unsplit spec, and it has one verifier round (20 of 27 claims confirmed, plan holds).
- Changed after the verifier on 2026-09-30: read-at moved from `c05ef6a` to `65906e2` (PR #27's head, merged into this branch at `68bd281`), and the Background and Risks wording updated. Part 2 cites no line of the two files the PR changed, and its counts were re-run and are unchanged.
- Changed after the verifier on 2026-09-30, from part 1's build: read-at moved from `65906e2` to `fa02c7c`; the counts re-run (117 live references in 32 files, 111 dated, 186 `~/notes`, the slash mentions unchanged at 107 in 23 files); `tests/skill-evals/run.sh:73-74` re-cited as `77-78`; and W3 now also removes the legacy spelling from `SCRIPTS` and `NET_SCRIPTS` and switches `review-state.py` to its absolute path with `skills/cold-review/SKILL.md`'s `allowed-tools`, both found by part 1's W2 (its record, Implementation). Its other findings (the private paths matched by resolved spelling, `build-index.py`'s header naming the script only, `agent-def.py --root` optional) need nothing here.

## Spikes

- Question 1: Route: deferred. Needs a model run (`claude -p --plugin-dir`), so credentials the spiker's sandbox denies. Run by hand by the user on 2026-09-29: EXPECTED; results in `docs/specs/spikes/2026-09-29-plugin-marketplace-2-cutover-results.md`.
- Question 7: Route: spike, added by the user's request on 2026-09-29 and run by hand: EXPECTED; results in `docs/specs/spikes/2026-09-29-plugin-marketplace-2-cutover-results.md`.
