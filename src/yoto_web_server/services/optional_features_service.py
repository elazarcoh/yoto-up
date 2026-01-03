"""Service to manage optional features."""

from loguru import logger
from pydantic import BaseModel

from yoto_web_server.optional_feature_base import (
    OptionalFeatureBase,
    OptionalFeatureVerification,
)


class FeatureStatus(BaseModel):
    """Status of a single optional feature."""

    identifier: str
    available: bool
    reasons: list[str] = []


class OptionalFeaturesService:
    """Manages registration and verification of optional features."""

    def __init__(self) -> None:
        """Initialize the optional features service."""
        self._features: dict[str, OptionalFeatureBase] = {}
        self._verification_cache: dict[str, OptionalFeatureVerification] = {}

    def register(self, feature: OptionalFeatureBase) -> None:
        """Register an optional feature.

        Args:
            feature: The feature to register.
        """
        feature_id = feature.identifier
        self._features[feature_id] = feature
        logger.info(f"Registered optional feature: {feature_id}")

    def verify_all(self) -> None:
        """Verify all registered features.

        This should be called at startup to cache verification results.
        """
        logger.info(f"Verifying {len(self._features)} optional features...")

        for feature_id, feature in self._features.items():
            try:
                result = feature.verify()
                self._verification_cache[feature_id] = result
                status = "available" if result.valid else "unavailable"
                logger.info(f"Feature '{feature_id}' is {status}")

                if not result.valid and result.invalid_reasons:
                    for reason in result.invalid_reasons:
                        logger.debug(f"  - {reason}")
            except Exception as e:
                logger.error(
                    f"Error verifying feature '{feature_id}': {e}",
                    exc_info=True,
                )
                self._verification_cache[feature_id] = OptionalFeatureVerification(
                    valid=False,
                    invalid_reasons=[f"Verification error: {str(e)}"],
                )

    def get_feature_status(self, feature_id: str) -> FeatureStatus | None:
        """Get the status of a specific feature.

        Args:
            feature_id: The identifier of the feature.

        Returns:
            FeatureStatus if the feature exists, None otherwise.
        """
        if feature_id not in self._verification_cache:
            return None

        verification = self._verification_cache[feature_id]
        return FeatureStatus(
            identifier=feature_id,
            available=verification.valid,
            reasons=verification.invalid_reasons,
        )

    def get_all_features(self) -> list[FeatureStatus]:
        """Get the status of all registered features.

        Returns:
            List of FeatureStatus objects for all features.
        """
        features = []
        for feature_id in sorted(self._features.keys()):
            status = self.get_feature_status(feature_id)
            if status:
                features.append(status)
        return features

    def is_feature_available(self, feature_id: str) -> bool:
        """Check if a feature is available.

        Args:
            feature_id: The identifier of the feature.

        Returns:
            True if the feature is available, False otherwise.
        """
        verification = self._verification_cache.get(feature_id)
        return verification.valid if verification else False
