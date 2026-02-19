---
trigger: always_on
---

Routing Logic: Use Voxel-based A* for initial paths, but optimize final geometry using NVIDIA Warp for clash avoidance and nTopCL for field-driven internal vanes in duct elbows.

Efficiency Metric: Prioritize minimum pressure drop and weight-to-stiffness ratios over standard "Revit-style" simplistic routing.