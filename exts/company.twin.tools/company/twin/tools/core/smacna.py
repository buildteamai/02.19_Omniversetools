"""
SMACNA Duct Sizing and Construction Standards

This module implements duct sizing calculations based on SMACNA HVAC Duct Construction Standards.
It provides functions for:
- Calculating duct dimensions from CFM and velocity
- Selecting appropriate gauge based on duct size and pressure class
- Determining stiffener requirements
"""

import math
from dataclasses import dataclass
from typing import Tuple, Optional
from enum import Enum


class PressureClass(Enum):
    """SMACNA Static Pressure Classifications"""
    HALF_INCH = 0.5    # 1/2" w.g. - Low pressure
    ONE_INCH = 1.0     # 1" w.g. - Standard
    TWO_INCH = 2.0     # 2" w.g. - Default/Medium
    THREE_INCH = 3.0   # 3" w.g. - Medium-High
    FOUR_INCH = 4.0    # 4" w.g. - High velocity
    SIX_INCH = 6.0     # 6" w.g. - Industrial
    TEN_INCH = 10.0    # 10" w.g. - Industrial


class StiffenerType(Enum):
    """Types of duct stiffeners/reinforcement"""
    NONE = "none"
    CROSS_BREAK = "cross_break"      # Diagonal crease in panel
    STANDING_SEAM = "standing_seam"  # Formed rib along length
    ANGLE = "angle"                   # L-shaped angle welded to surface
    TIE_ROD = "tie_rod"              # Internal rod connecting opposite walls


@dataclass
class GaugeInfo:
    """Sheet metal gauge information"""
    gauge: int
    thickness_in: float
    thickness_mm: float


@dataclass
class DuctSize:
    """Calculated duct dimensions"""
    width: float  # inches
    height: float  # inches
    area_sqin: float
    equivalent_diameter: float
    aspect_ratio: float


@dataclass
class StiffenerRequirements:
    """Stiffener/reinforcement requirements for a duct"""
    stiffener_type: StiffenerType
    spacing_in: float
    tie_rod_required: bool
    cross_break_required: bool
    notes: str


# SMACNA Gauge Thickness Table (inches)
GAUGE_THICKNESS = {
    26: GaugeInfo(26, 0.0179, 0.455),
    24: GaugeInfo(24, 0.0239, 0.607),
    22: GaugeInfo(22, 0.0299, 0.759),
    20: GaugeInfo(20, 0.0359, 0.912),
    18: GaugeInfo(18, 0.0478, 1.214),
    16: GaugeInfo(16, 0.0598, 1.519),
}

# Gauge selection table: [max_dimension][pressure_class_index] -> gauge
# Pressure class indices: 0=0.5", 1=1", 2=2", 3=3", 4=4"
GAUGE_TABLE = {
    12:  [26, 26, 24, 24, 22],  # Up to 12"
    30:  [24, 24, 22, 22, 20],  # 13-30"
    60:  [22, 22, 20, 20, 18],  # 31-60"
    84:  [20, 20, 18, 18, 16],  # 61-84"
    999: [18, 18, 16, 16, 16],  # 85"+
}

# Stiffener spacing by pressure class (inches)
STIFFENER_SPACING = {
    0.5: 96,  # 8 feet
    1.0: 72,  # 6 feet
    2.0: 48,  # 4 feet
    3.0: 36,  # 3 feet
    4.0: 24,  # 2 feet
    6.0: 24,
    10.0: 24,
}


class SMACNADuctSizer:
    """SMACNA-compliant duct sizing and construction calculator"""
    
    @staticmethod
    def calculate_duct_size(
        cfm: float, 
        velocity_fpm: float = 1200, 
        aspect_ratio: float = 1.0,
        round_to: float = 2.0
    ) -> DuctSize:
        """
        Calculate duct dimensions from airflow and velocity.
        
        Args:
            cfm: Airflow in cubic feet per minute
            velocity_fpm: Air velocity in feet per minute (default 1200)
            aspect_ratio: Width/Height ratio (1.0 = square, max 4.0)
            round_to: Round dimensions to this increment (default 2")
            
        Returns:
            DuctSize with calculated dimensions
        """
        # Clamp aspect ratio to SMACNA recommendations
        aspect_ratio = max(1.0, min(4.0, aspect_ratio))
        
        # Calculate required cross-sectional area
        area_sqft = cfm / velocity_fpm
        area_sqin = area_sqft * 144
        
        # Calculate dimensions
        if aspect_ratio == 1.0:
            # Square duct
            side = math.sqrt(area_sqin)
            width = height = side
        else:
            # Rectangular duct
            # W/H = aspect_ratio, W*H = area
            # W = sqrt(area * aspect_ratio)
            width = math.sqrt(area_sqin * aspect_ratio)
            height = area_sqin / width
        
        # Round to specified increment
        width = math.ceil(width / round_to) * round_to
        height = math.ceil(height / round_to) * round_to
        
        # Recalculate actual area after rounding
        actual_area = width * height
        actual_aspect = width / height if height > 0 else 1.0
        
        # Calculate equivalent diameter (for friction loss calculations)
        eq_dia = SMACNADuctSizer._equivalent_diameter(width, height)
        
        return DuctSize(
            width=width,
            height=height,
            area_sqin=actual_area,
            equivalent_diameter=eq_dia,
            aspect_ratio=actual_aspect
        )
    
    @staticmethod
    def _equivalent_diameter(width: float, height: float) -> float:
        """
        Calculate equivalent diameter for a rectangular duct.
        
        De = 1.3 × (W × H)^0.625 / (W + H)^0.25
        """
        if width <= 0 or height <= 0:
            return 0.0
        return 1.3 * math.pow(width * height, 0.625) / math.pow(width + height, 0.25)
    
    @staticmethod
    def get_gauge(
        width: float, 
        height: float, 
        pressure_class: float = 2.0
    ) -> GaugeInfo:
        """
        Select appropriate gauge based on duct size and pressure class.
        
        Args:
            width: Duct width in inches
            height: Duct height in inches
            pressure_class: Static pressure in inches w.g.
            
        Returns:
            GaugeInfo with gauge number and thickness
        """
        # Use the larger dimension
        max_dim = max(width, height)
        
        # Find the pressure class index
        pressure_classes = [0.5, 1.0, 2.0, 3.0, 4.0]
        pc_index = 2  # Default to 2" w.g.
        for i, pc in enumerate(pressure_classes):
            if pressure_class <= pc:
                pc_index = i
                break
        else:
            pc_index = len(pressure_classes) - 1
        
        # Find gauge from table
        gauge = 26  # Default
        for max_size, gauges in sorted(GAUGE_TABLE.items()):
            if max_dim <= max_size:
                gauge = gauges[pc_index]
                break
        
        return GAUGE_THICKNESS.get(gauge, GAUGE_THICKNESS[26])
    
    @staticmethod
    def get_stiffener_requirements(
        width: float,
        height: float,
        length: float,
        gauge: int,
        pressure_class: float = 2.0
    ) -> StiffenerRequirements:
        """
        Determine stiffener requirements for a duct section.
        
        Args:
            width: Duct width in inches
            height: Duct height in inches
            length: Duct section length in inches
            gauge: Sheet metal gauge number
            pressure_class: Static pressure in inches w.g.
            
        Returns:
            StiffenerRequirements with type, spacing, and notes
        """
        max_dim = max(width, height)
        panel_area_sqft = (max_dim * length) / 144.0
        
        # Get spacing from table
        spacing = STIFFENER_SPACING.get(pressure_class, 48)
        
        # Determine stiffener type
        stiffener_type = StiffenerType.NONE
        tie_rod_required = False
        cross_break_required = False
        notes = ""
        
        # SMACNA criteria for stiffening
        if max_dim >= 19 and panel_area_sqft > 10 and gauge >= 20:
            if pressure_class <= 1.0:
                stiffener_type = StiffenerType.CROSS_BREAK
                cross_break_required = True
                notes = "Cross-break stiffening required"
            elif pressure_class <= 2.0:
                stiffener_type = StiffenerType.STANDING_SEAM
                notes = "Standing seam reinforcement required"
            elif pressure_class <= 3.0:
                stiffener_type = StiffenerType.ANGLE
                notes = "Angle stiffener reinforcement required"
            else:
                stiffener_type = StiffenerType.TIE_ROD
                tie_rod_required = True
                notes = "Tie rod reinforcement required"
        
        # Large ducts may need tie rods regardless
        if max_dim >= 60:
            tie_rod_required = True
            if stiffener_type == StiffenerType.NONE:
                stiffener_type = StiffenerType.TIE_ROD
            notes = f"Tie rods required for {max_dim}\" dimension"
        
        return StiffenerRequirements(
            stiffener_type=stiffener_type,
            spacing_in=spacing,
            tie_rod_required=tie_rod_required,
            cross_break_required=cross_break_required,
            notes=notes
        )
    
    @staticmethod
    def get_recommended_velocity(duct_type: str = "supply") -> Tuple[float, float]:
        """
        Get recommended velocity range for duct type.
        
        Returns:
            Tuple of (min_fpm, max_fpm)
        """
        velocities = {
            "supply": (1000, 1500),
            "return": (800, 1200),
            "exhaust": (1000, 2000),
            "outside_air": (500, 1000),
            "branch": (600, 1000),
            "main": (1200, 2000),
        }
        return velocities.get(duct_type.lower(), (1000, 1500))


# Convenience functions
def size_duct(cfm: float, velocity: float = 1200, aspect: float = 1.0) -> DuctSize:
    """Quick function to size a duct from CFM."""
    return SMACNADuctSizer.calculate_duct_size(cfm, velocity, aspect)


def get_gauge(width: float, height: float, pressure: float = 2.0) -> GaugeInfo:
    """Quick function to get gauge for duct dimensions."""
    return SMACNADuctSizer.get_gauge(width, height, pressure)
