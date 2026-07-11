# Grounded Annotation Guidelines

Annotate only what is explicit at the end of the displayed event window. Do not use
later trajectory outcomes to reconstruct what the agent supposedly believed.

## Claim boundary

A Claim is a proposition about the repository, failure, fix, or expected effect.
“Inspect parser.py” is an Action, not the Claim “parser.py is the root cause.” If no
proposition is explicit, mark `claim` in `abstained_kinds`.

Every Claim and Evidence item must copy an exact source span. Record event ID, start
offset, end offset, and the event content hash. Paraphrases may be stored as
`canonical_text`, but never as `exact_span`.

## Statuses and relations

- `candidate`: explicitly proposed but not adopted or supported.
- `active`: explicitly adopted, or supported by verified evidence.
- `refuted`: directly contradicted by verified evidence.
- `accepted`: target test passes after the fix and relevant regression checks pass.

Evidence relations are `supports`, `contradicts`, or `neutral` during annotation.
Neutral relations are retained in the annotation but are not inserted into the state
graph.

## Failure labels

- `ineffective_patch`: target failure does not improve, a regression is introduced,
  or the patch is fully reverted.
- `unsupported_patch`: no active Claim and no verified Evidence justifies the edit.
- `repeated_exploration`: the same file/region is revisited within 20 actions without
  a new Claim, Evidence, failure, or information need.
- `continued_after_refutation`: an Action still depends on a refuted Claim and no new
  evidence has reopened it.
- `premature_finish`: an explicit Constraint remains unresolved, the latest target
  test fails, or edited code has no successful functional verification.

The primary annotator labels all 200 windows. A second annotator independently labels
40 randomly selected windows. Freeze the dataset only when Cohen's kappa is at least
0.75 and provenance span F1 is at least 0.85.
