# Record: {{spec title}}

What happened to [{{spec basename}}](../{{spec basename}}.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan. Sections appear as they're needed, in this order; leave out any that have nothing in them yet.

## Verification

- {{YYYY-MM-DD}}: spec-verifier, {{N}} of {{M}} claims confirmed. Plan holds: {{yes | no, and why}}.
- Verifier round 2 ran on {{YYYY-MM-DD}}: after {{verification | the cold review | spikes}}, re-checking {{Wn, Wm}}.

## Cold review

Reviewed on {{YYYY-MM-DD}} by cold-reviewer. Saved unchanged; what was folded in is logged under Changes since the review.

{{the reviewer's table and closing lines, unchanged}}

### Delta review, {{YYYY-MM-DD}}

Reviewed on {{YYYY-MM-DD}} by cold-reviewer: the changes logged as Not reviewed. Saved unchanged.

## Changes since the review

- Not reviewed: {{what changed}}, from {{cold review row n | spike S<n> | the user}}, on {{YYYY-MM-DD}}.

## Spikes

- Question {{n}}: Route: {{spike | research | decision | deferred}}. Changes: {{the work items and quoted claims that change with the answer}}. Expect: {{what the experiment should show, written before it ran}}. Box: {{$2, 60 turns; hosts: none}}.

## Implementation

- {{YYYY-MM-DD}}, {{Wn}} ({{commit}}): {{what the build did differently from the spec, and why}}.
