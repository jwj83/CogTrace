GROUNDED_EXTRACTION_PROMPT = """You extract cognitive state from agent events.

Return only JSON. Extract explicit Goal, Constraint, Claim, and Decision nodes.
Every node must copy an exact source span and include event_id, span_start,
span_end, and content_hash. Do not turn an inspection action into a root-cause
claim. Do not infer beliefs from later events. If a kind is not explicit, add it
to abstained_kinds. Evidence relations may be supports, contradicts, satisfies,
violates, or justifies; ambiguous relations must be marked proposed.
"""
