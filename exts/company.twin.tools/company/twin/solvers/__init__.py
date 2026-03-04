# Solvers Package
# This package contains the logic for constraint solvers and generative design tools.
from .fan_classifier import FanClassificationSolver, FanDesignPoint, FanClassification
from .impeller_aero import ImpellerAeroSolver, ImpellerAeroResult
from .volute_solver import VoluteSolver, VoluteResult
from .fan_structural import FanStructuralSolver, FanStructuralResult
from .fan_acoustic import FanAcousticSolver, FanAcousticResult
