from enum import Enum


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    APPROVED = "approved"
    REJECTED = "rejected"


class TaskComplexity(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    CRITICAL = "critical"


class QualityRating(str, Enum):
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    GOOD = "good"
    EXCELLENT = "excellent"


COMPLEXITY_BASE_POINTS = {
    TaskComplexity.SMALL: 5,
    TaskComplexity.MEDIUM: 15,
    TaskComplexity.LARGE: 35,
    TaskComplexity.CRITICAL: 60,
}

QUALITY_MULTIPLIERS = {
    QualityRating.REJECTED: 0.0,
    QualityRating.ACCEPTED: 1.0,
    QualityRating.GOOD: 1.2,
    QualityRating.EXCELLENT: 1.5,
}
