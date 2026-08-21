from dataclasses import dataclass

from zhaoniu_api.config import Settings


@dataclass(frozen=True, slots=True)
class DatasetPolicyDecision:
    allowed: bool
    policy_version: str
    reason_code: str | None = None


class DatasetPolicyRegistry:
    """Executable policy gate. Markdown policy documents are descriptive, not runtime input."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def version(self) -> str:
        return self._settings.coverage_policy_version

    def decide(self, dimension: str) -> DatasetPolicyDecision:
        if dimension == "ai_research":
            return DatasetPolicyDecision(True, self.version)
        if self._settings.coverage_usage_scope == "development_evaluation":
            return DatasetPolicyDecision(True, self.version)
        return DatasetPolicyDecision(False, self.version, "policy_development_source_only")
