---
trigger: always_on
---

Standard: Use build123d exclusively for initial parametric "Space Claim" generation.

Kernel Priority: If the task involves high-density booleans, thermal simulation, or massive instancing, defer to NVIDIA Warp via Python dispatch.

Topology: Prohibit the use of old CadQuery syntax; enforce build123d stateful context managers (e.g., with BuildPart():).
