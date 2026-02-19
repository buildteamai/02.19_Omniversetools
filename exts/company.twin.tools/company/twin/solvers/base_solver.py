
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseSolver(ABC):
    """
    Abstract Base Class for all Constraint Solvers.
    
    A Solver takes a dictionary of inputs (parameters, constraints)
    and returns a dictionary of outputs (geometry data, transforms, metadata).
    
    Each Solver represents a specific engineering domain (Frame, Duct, Wall).
    """
    
    @abstractmethod
    def solve(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the solver logic.
        
        Args:
            inputs: Dictionary containing all necessary parameters for the calculation.
                    Example: {'width': 100, 'height': 200, 'load': 50}
                    
        Returns:
            Dictionary containing the results.
            Standardized Keys:
            - 'parts': Dict[str, build123d.Solid] - The generated geometry
            - 'transforms': Dict[str, build123d.Location] - The placement of parts
            - 'anchors': Dict[str, Dict[str, Tuple]] - Connection points for other solvers
            - 'metadata': Dict[str, Any] - Engineering data (weight, cost, etc.)
        """
        pass

    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """
        Optional: Validate inputs before solving.
        Override this method to enforce specific constraints.
        Returns True if valid, raises ValueError if invalid.
        """
        return True
