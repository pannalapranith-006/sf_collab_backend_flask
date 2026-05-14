from datetime import datetime, timezone
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from app.models.task import (
    TaskComplexity,
    QualityRating,
    COMPLEXITY_BASE_POINTS,
    QUALITY_MULTIPLIERS,
)

# Threshold: completed >= 24 hours before deadline counts as "early"
EARLY_THRESHOLD_SECONDS = 86400

# Maximum allowed length for proof_status strings
_PROOF_STATUS_APPROVED = "approved"


def _ensure_aware(dt: datetime) -> datetime:
    """
    Return *dt* as a timezone-aware datetime.

    Naive datetimes are assumed to be UTC.  Already-aware datetimes are
    returned unchanged.  This is applied unconditionally (not just when
    the value came from a string) so that callers who pass pre-built
    datetime objects with mixed awareness don't slip through.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def calculate_deadline_multiplier(task_deadline, completed_at):
    """
    MVP deadline multipliers:
      early  (>=24 h before deadline) -> 1.1
      on time (0 .. <24 h before)     -> 1.0
      late   (after deadline)         -> 0.7

    Both naive and aware datetimes are accepted; naive values are
    treated as UTC.  Mixed-awareness pairs (one naive, one aware) are
    normalised before subtraction to avoid TypeError.
    """
    if task_deadline is None or completed_at is None:
        return 1.0

    if isinstance(task_deadline, str):
        task_deadline = datetime.fromisoformat(task_deadline)
    if isinstance(completed_at, str):
        completed_at = datetime.fromisoformat(completed_at)

    # FIX: normalise tz-awareness unconditionally, not only for str inputs.
    # Without this, callers who pass a naive datetime object alongside an
    # aware one trigger: TypeError: can't subtract offset-naive and
    # offset-aware datetimes.
    task_deadline = _ensure_aware(task_deadline)
    completed_at = _ensure_aware(completed_at)

    delta = (task_deadline - completed_at).total_seconds()

    if delta >= EARLY_THRESHOLD_SECONDS:
        return 1.1
    if delta >= 0:
        return 1.0
    return 0.7


def calculate_proof_multiplier(requires_proof, proof_status):
    """
    MVP proof multipliers:
      no proof required          -> 1.0
      proof approved (any case)  -> 1.25
      proof missing / other      -> None  (caller must raise / hold)

    FIX: comparison is now case-insensitive so "Approved" / "APPROVED"
    are treated the same as "approved".
    """
    if not requires_proof:
        return 1.0
    # FIX: normalise case before comparing so "Approved" / "APPROVED" work.
    if isinstance(proof_status, str) and proof_status.strip().lower() == _PROOF_STATUS_APPROVED:
        return 1.25
    return None


@dataclass
class PointsInput:
    """Groups inputs to compute_task_points to avoid too-many-arguments."""
    complexity: str
    quality_rating: str
    requires_proof: bool
    proof_status: str | None
    task_deadline: str | datetime | None = None
    completed_at: str | datetime | None = None


def compute_task_points(inputs: PointsInput) -> dict:
    """
    Final Points = Base × Quality × Proof × Deadline

    Accepts a PointsInput dataclass to keep the call signature clean.

    Raises ValueError if:
      - complexity or quality_rating are invalid enum values
      - quality_rating is 'rejected' (use reject_task() instead)
      - proof is required but not yet approved

    FIX: enum construction now happens inside an explicit try/except so
    that the subsequent guard checks (if base is None / if quality_mult
    is None) are actually reachable.  Previously, TaskComplexity("huge")
    raised ValueError before .get() was ever called, making those guards
    dead code.
    """
    # Guard before enum validation: "rejected" is a valid QualityRating value,
    # but should never reach point calculation. Checked early so callers get a
    # clear message pointing to reject_task() rather than a generic enum error.
    if inputs.quality_rating == QualityRating.REJECTED:
        raise ValueError(
            "Cannot compute points for a rejected quality rating. "
            "Use reject_task() to zero out points."
        )

    # FIX: validate enum membership explicitly so the guard below is live code.
    try:
        complexity_enum = TaskComplexity(inputs.complexity)
    except ValueError as exc:
        raise ValueError(f"Unknown complexity: '{inputs.complexity}'. "
                         f"Valid values: {[c.value for c in TaskComplexity]}") from exc

    try:
        quality_enum = QualityRating(inputs.quality_rating)
    except ValueError as exc:
        raise ValueError(f"Unknown quality rating: '{inputs.quality_rating}'. "
                         f"Valid values: {[q.value for q in QualityRating]}") from exc

    base = COMPLEXITY_BASE_POINTS.get(complexity_enum)
    if base is None:
        # Should never happen once the enum is valid, but keeps the guard live.
        raise ValueError(f"No base points configured for complexity: {inputs.complexity}")

    quality_mult = QUALITY_MULTIPLIERS.get(quality_enum)
    if quality_mult is None:
        raise ValueError(f"No multiplier configured for quality rating: {inputs.quality_rating}")

    proof_mult = calculate_proof_multiplier(inputs.requires_proof, inputs.proof_status)
    if proof_mult is None:
        raise ValueError(
            "Task requires approved proof before points can be granted. "
            f"Current proof_status: {inputs.proof_status!r}"
        )

    deadline_mult = calculate_deadline_multiplier(inputs.task_deadline, inputs.completed_at)
    final = float(
        (Decimal(str(base)) * Decimal(str(quality_mult))
         * Decimal(str(proof_mult)) * Decimal(str(deadline_mult)))
        .quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    )

    return {
        "base_points": base,
        "quality_multiplier": quality_mult,
        "proof_multiplier": proof_mult,
        "deadline_multiplier": deadline_mult,
        "final_points": final,
    }
