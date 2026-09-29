# Record: Install the skills from the Claude Code plugin marketplace, part 2: cutover

What happened to [2026-09-29-plugin-marketplace-2-cutover](../2026-09-29-plugin-marketplace-2-cutover.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan. Sections appear as they're needed, in this order; leave out any that have nothing in them yet.

This spec is part 2 of 2, split on 2026-09-29 from [2026-09-29-plugin-marketplace](../2026-09-29-plugin-marketplace.md), which was verified in three rounds and given a full cold review and one delta review as a single document. That history is in [its record] and covers this part's text as it stood before the split; the split only regrouped that text into two parts, adding each part's Goal, the "Both layouts" Decision bullet in part 1 and the Prerequisite line in part 2, and correcting cross-references. No claim was changed. This part has no saved cold review of its own.

## Verification

- 2026-09-29: spec-verifier, 20 of 27 claims confirmed. Plan holds: yes.
  - Fixed: the 23-file count carries its `-l` derivation; the plugin-name claim now says part 1's W1 names the plugin; "plugins can't ship permission or sandbox settings" is marked *(unverified)*; W3's Done when says the versioned cache path is untested; `docs/containment.md` in W5 says why it is listed; W4's Effort dependency says "and so part 1".
  - Not applied, and why: `CLAUDE.md:32-33` (the rule's bullet starts at line 33, so `:33` is right) and `skills/spec/SKILL.md:6-10` (the `allowed-tools` value ends at line 9; line 10 is the closing `---`).
  - Not checked by the verifier, and checked here: "draft PR #27, open" (`gh pr view 27` on 2026-09-29: open, draft).
- Changed after the verifier on 2026-09-30: W3's Done when for `check-spec.py` over `docs/specs/` now says every spec that passed before still passes, since two older specs fail for missing notes in `~/notes`, from part 1's delta review row 4.

## Spikes

- Question 1: Route: deferred. Needs a model run (`claude -p --plugin-dir`), so credentials the spiker's sandbox denies. Run by hand by the user on 2026-09-29: EXPECTED; results in `docs/specs/spikes/2026-09-29-plugin-marketplace-2-cutover-results.md`.
- Question 7: Route: spike, added by the user's request on 2026-09-29 and run by hand: EXPECTED; results in `docs/specs/spikes/2026-09-29-plugin-marketplace-2-cutover-results.md`.
