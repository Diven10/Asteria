import abc
from app.contracts.models import LightCurve, DetectionCandidate

class TransitDetector(abc.ABC):
    """Pluggable interface for transit detection algorithms."""
    
    @abc.abstractmethod
    def detect(self, lc: LightCurve) -> list[DetectionCandidate]:
        """Detect transit candidates in the given light curve."""
        pass
