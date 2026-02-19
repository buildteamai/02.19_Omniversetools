
# Design Journal & Vision Board

**Purpose**: This document is our "Clean Room." A place to discuss aesthetics, system architecture, and high-level goals without the pressure of writing compilable code.

## Entry 001 to 008
*(See previous entries)*

---

## Entry 009: Engineering Math (The Validation Layer)
**Date**: 2026-02-14

### The Question
> "In the steel frame generator can we introduce simple deflection calculations that validate the leg, connection, and header beam sizes? Do you understand what calculations we would need?"

### The Answer: Yes, we need "Simply Supported Beam" Math.
We will implement checks based on **AISC 360-16** simplifications.

**1. The Inputs**:
- `E` (Modulus of Elasticity): `29,000 ksi` (Standard for Steel).
- `Fy` (Yield Strength): `50 ksi` (A992/A500).
- `Load` (w): Uniform Load (`kips/in`) along the header. Default to `100 lbs/ft`?
- `Unbraced Length` (Lx, Ly): `Header Length` and `Column Height`.

**2. The Calculations (Header)**:
- **Moment of Inertia (Ix)**: Retrieved from Profile Data.
- **Section Modulus (Sx)**: Retrieved from Profile Data.
- **Max Moment (M)**: $M = \frac{wL^2}{8}$
- **Bending Stress (fb)**: $f_b = \frac{M}{S_x}$ -> Check against $0.66 \times F_y$ (ASD) or $0.9 \times F_y$ (LRFD).
- **Deflection (Delta)**: $\delta = \frac{5wL^4}{384EI_x}$
- **Criteria**: Is $\delta < \frac{L}{360}$? (Or L/240).

**3. The Calculations (Columns)**:
- **Axial Load (P)**: Reaction from Header ($R = \frac{wL}{2}$).
- **Area (A)**: Retrieved from Profile.
- **Axial Stress (fa)**: $f_a = \frac{P}{A}$.
- **Slenderness (KL/r)**: $K=1.0$ (Pinned-Pinned), $L=Height$, $r=min(r_x, r_y)$.
- **Buckling Check**: If $\frac{KL}{r} > 200$, Fail. Else calculate Allowable Stress ($F_a$).

**4. The Result**:
The Solver returns `metadata['validation']`:
```json
{
  "header_deflection": 0.45,
  "allowable_deflection": 0.66,
  "status": "PASS",
  "column_stress_ratio": 0.12
}
```
If `status` is "FAIL", we color the frame **RED** in the viewport.
