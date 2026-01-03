import abc
from typing import ClassVar

from pydantic import BaseModel


class OptionalFeatureVerification(BaseModel):
    valid: bool
    invalid_reasons: list[str] = []


class OptionalFeatureBase(abc.ABC):
    """Base class for optional features in the Yoto web server."""

    identifier: ClassVar[str]

    @abc.abstractmethod
    def verify(self) -> OptionalFeatureVerification:
        """Verify if the optional feature is correctly set up.

        Returns:
            OptionalFeatureVerification: The result of the verification.
        """
        pass
