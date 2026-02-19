# SPDX-FileCopyrightText: Copyright (c) 2024-2026 BuildTeam AI. All rights reserved.
# SPDX-License-Identifier: Proprietary

"""
Steel Connection Module

Provides AISC-compliant connection rules, geometry generators, and utilities.
"""

from .connection_rules import (
    ConnectionType,
    MemberType,
    ConnectionSurface,
    ConnectionRules,
    ConnectionDesign,
    BoltSpec,
    PlateSpec,
    WeldSpec,
    get_connection_rules
)

from .shear_tab import ShearTabGenerator
from .double_angle import DoubleAngleGenerator
from .gusset_plate import GussetPlateGenerator

__all__ = [
    'ConnectionType',
    'MemberType', 
    'ConnectionSurface',
    'ConnectionRules',
    'ConnectionDesign',
    'BoltSpec',
    'PlateSpec',
    'WeldSpec',
    'get_connection_rules',
    'ShearTabGenerator',
    'DoubleAngleGenerator',
    'GussetPlateGenerator'
]
