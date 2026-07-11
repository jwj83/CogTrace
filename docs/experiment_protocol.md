# Frozen CogTrace-B Experiment Protocol

## Data

Collect 240 evaluated trajectories across at least ten repositories. Split by
repository, never by window: 60% train, 20% development, 20% test. The ten legacy
Astropy traces are development/regression cases only.

## Representation comparison

Use identical model, system prompt, tools, action limit, and total input-token cap:

- Raw: recent original history.
- Summary: recent raw events plus LLM summary.
- CogTrace: recent raw events plus grounded state and provenance-linked Evidence.

Primary total-window conditions are 128K for the open 14B model and 512K for the
DeepSeek V4 reproduction. State payload ablations are 4K, 16K, and 32K. Do not call
a 4K state payload a 4K agent context.

## Confirmatory runs

Use 80 SWE-bench Verified and 80 SWE-bench Pro instances, two rollouts per condition.
Report official resolve rate, token use, steps, wall time, claim revision, four failure
rates, guard precision, and false blocks. Bootstrap whole trajectories/tasks rather
than individual windows.

## Gates

- Extraction: precision >= .90, span F1 >= .90, transition macro-F1 >= .80,
  abstention F1 >= .80, hallucination <= .05.
- Prediction: macro-AUPRC gain >= .05; at least two per-failure confidence intervals
  exclude zero.
- Online: +3 resolved percentage points, or -20% key failures with at most -1 point
  resolve regression; CogTrace overhead <=20% of agent tokens.

All configurations, revisions, seeds, raw traces, extractor responses, snapshots,
official evaluator outputs, and bootstrap samples must be retained.
