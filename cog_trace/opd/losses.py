from __future__ import annotations

from typing import Any


def reverse_kl_topk(student_logits: Any, teacher_topk_indices: Any, teacher_topk_logprobs: Any):
    """Approximate reverse KL on teacher top-k support.

    Torch is imported lazily so the state/annotation package remains lightweight.
    The caller is responsible for aligning tensors as [batch, sequence, k].
    """
    import torch

    student_logprobs = torch.log_softmax(student_logits, dim=-1)
    selected_student = torch.gather(student_logprobs, -1, teacher_topk_indices)
    teacher_probs = torch.exp(teacher_topk_logprobs)
    teacher_probs = teacher_probs / teacher_probs.sum(dim=-1, keepdim=True).clamp_min(1e-12)
    normalized_teacher_logprobs = torch.log(teacher_probs.clamp_min(1e-12))
    selected_student_probs = torch.exp(selected_student)
    selected_student_probs = selected_student_probs / selected_student_probs.sum(
        dim=-1, keepdim=True
    ).clamp_min(1e-12)
    selected_student_logprobs = torch.log(selected_student_probs.clamp_min(1e-12))
    return (
        (selected_student_probs * (selected_student_logprobs - normalized_teacher_logprobs))
        .sum(dim=-1)
        .mean()
    )
