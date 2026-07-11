# Single-Host Failure-Conditioned OPD

The official pipeline uses only the machine with eight RTX PRO 6000 Blackwell 96GB
GPUs. The four-A800 machine is a cold fallback and is never part of a distributed job.

## Modes

1. Rollout/evaluation: GPUs 0–3 serve/run 14B students; GPUs 4–7 serve the 32B
   extractor or teacher.
2. Training: stop all inference services and use GPUs 0–7 for the 14B student.
3. Evaluation: stop training, restart frozen inference services, and evaluate the new
   checkpoint.

Use local NVMe for trajectories, top-64 teacher log probabilities, and checkpoints.
No online request may depend on the other machine.

## Data safety

Generate two rounds of 2,500 on-policy rollouts from SWE-smith or repository-disjoint
training tasks. CogTrace runs in shadow mode. Select at most the first three failure
states per trajectory and target approximately 10,000 states. The OPD schema rejects
SWE-bench Verified and SWE-bench Pro as training sources.

Compare base, random-state OPD, equal-budget full-trajectory distillation,
failure-conditioned SFT/DPO, and strict reverse-KL OPD. SFT on a teacher correction is
not labeled OPD; strict OPD requires teacher token distributions on student-generated
continuations.
