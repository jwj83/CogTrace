# CogTrace V1 Method

> Legacy note: this document describes the pre-grounding rule-based prototype.
> Its outputs remain useful as case studies but are not part of the grounded-v1
> confirmatory evaluation. The current method and gates are documented in
> `experiment_protocol.md`.

CogTrace models an agent trajectory as a stream of cognitive commitments. It extracts
goals, constraints, hypotheses, decisions, patches, tests, and evidence; stores them
in a cognitive state graph; and triggers guards when later actions conflict with, or
forget, earlier active commitments.

## Event Triggers

- `task_start`: extract the issue goal and explicit issue constraints.
- `strong_cognitive_thought`: extract hypotheses, constraints, or decisions when the
  thought contains strong cognitive markers such as `root cause`, `because`,
  `therefore`, `should`, `correct fix`, `issue says`, `version`, or
  `expected behavior`.
- `code_edit`: extract patch/decision nodes and check whether the edit contradicts
  active hypotheses or constraints.
- `test_result`: extract evidence and run contradiction checks.
- `repeated_exploration`: cheap non-LLM signal. If the same file is read repeatedly
  while a high-confidence non-generic hypothesis is still active and unresolved,
  emit a context reminder.
- `finish`: final safety check for unresolved early high-confidence hypotheses.

## Graph Semantics

Nodes:

- `Goal`
- `Constraint`
- `Hypothesis`
- `Decision`
- `Patch`
- `TestResult`
- `Evidence`
- `CodeEntity`

Edges:

- `supports`
- `refutes`
- `contradicts`
- `implements`
- `tests`
- `mentions`
- `violates`
- `resolves`
- `derived_from`

## V1 Conservative Rules

The current implementation is deterministic and intentionally conservative. It uses
rule-based extraction for the first two target cases:

- `astropy__astropy-13236`: detects the repository-version commitment that the
  structured ndarray auto-transform clause should be removed in 5.2, then flags the
  later warning-only patch that keeps `data.view(NdarrayMixin)`.
- `astropy__astropy-13033`: detects the root-cause hypothesis that
  `_check_required_columns` hardcodes `required_columns[0]`, then emits a repeated
  exploration reminder when the agent keeps reading related files before acting.

Generic planning thoughts are marked with `metadata.generic = true` and ignored by
repeated-exploration and finish reminders, which keeps V1 from treating vague
planning as a strong cognitive commitment.

## Reproduce

Run CogTrace over the local OpenHands trajectories:

```powershell
python scripts\replay_offline.py
python scripts\analyze_results.py
```

Render the two core case reports:

```powershell
python scripts\render_case_report.py --instance astropy__astropy-13236
python scripts\render_case_report.py --instance astropy__astropy-13033
```

Outputs are written under `artifacts/cogtrace/<instance>/`.

## Current Evidence

On the 10 local OpenHands trajectories:

- `astropy__astropy-13236`: 2 contradiction edges and 1 repeated-exploration reminder.
- `astropy__astropy-13033`: 0 contradictions and 1 repeated-exploration reminder.
- The other 8 trajectories produce no reminders after generic-hypothesis filtering.

This gives V1 two clean paper examples:

- Cognitive contradiction: the agent knew the correct phase-specific behavior, then
  implemented a patch that violated that commitment.
- Cognitive context failure: the agent found the likely root cause, then spent more
  steps re-reading related context before implementing the known commitment.
