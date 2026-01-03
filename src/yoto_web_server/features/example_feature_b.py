"""Example Feature B - demonstrates optional feature system."""

from typing import ClassVar

from yoto_web_server.optional_feature_base import (
    OptionalFeatureBase,
    OptionalFeatureVerification,
)


class ExampleFeatureB(OptionalFeatureBase):
    """Example optional feature B for POC demonstration.

    This feature is intentionally disabled to showcase UI
    with unavailable features.
    """

    identifier: ClassVar[str] = "example_feature_b"

    def __init__(self, available: bool = False) -> None:
        """Initialize Example Feature B.

        Args:
            available: Whether this feature should be available.
        """
        self._available = available

    def verify(self) -> OptionalFeatureVerification:
        """Verify if Example Feature B is available.

        Returns:
            OptionalFeatureVerification: Valid if feature is available.
        """
        if self._available:
            return OptionalFeatureVerification(valid=True)

        return OptionalFeatureVerification(
            valid=False,
            invalid_reasons=[
                "Example Feature B is not available in this deployment",
                "This feature requires additional configuration",
            ],
        )
