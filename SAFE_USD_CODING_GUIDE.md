# Safe USD Coding Guide

## Quick Reference for Preventing TF_PYTHON_EXCEPTION Errors

This guide provides patterns for safe USD attribute access to prevent `TF_PYTHON_EXCEPTION` errors in Omniverse extensions.

---

## ❌ NEVER Do This

```python
# UNSAFE - Will crash if attribute doesn't exist
value = prim.GetAttribute("my_attr").Get()

# UNSAFE - Chaining without validation
system = prim.GetAttribute("antigravity:system_type").Get()

# UNSAFE - Assuming attribute has value
if prim.HasAttribute("my_attr"):
    value = prim.GetAttribute("my_attr").Get()  # Still unsafe! HasAttribute != HasValue
```

---

## ✅ ALWAYS Do This

### Method 1: Manual Validation (Verbose but Clear)

```python
# SAFE - Check both attribute existence and value
attr = prim.GetAttribute("my_attr")
if attr and attr.HasValue():
    value = attr.Get()
else:
    value = default_value  # Handle missing case
```

### Method 2: Use USD Helpers (Recommended)

```python
from company.twin.tools.antigravity.core.usd_helpers import get_attr_safe

# SAFE - One-liner with default
value = get_attr_safe(prim, "my_attr", default_value)

# SAFE - Check if exists with value
if has_attr_with_value(prim, "my_attr"):
    # Safe to access
    pass
```

---

## Common Patterns

### 1. Reading a Single Attribute

```python
# Using helper (recommended)
cfm = get_attr_safe(prim, "antigravity:system:thermal:cfm", 0.0)

# Manual approach
cfm_attr = prim.GetAttribute("antigravity:system:thermal:cfm")
if cfm_attr and cfm_attr.HasValue():
    cfm = cfm_attr.Get()
else:
    cfm = 0.0
```

### 2. Reading Multiple Attributes

```python
from company.twin.tools.antigravity.core.usd_helpers import get_attrs_safe

# Get multiple attributes at once
attrs = get_attrs_safe(prim, [
    "antigravity:system_type",
    "antigravity:flow_direction",
    "antigravity:port_radius"
], defaults=["Unknown", "inlet", 6.0])

system_type = attrs["antigravity:system_type"]
flow_dir = attrs["antigravity:flow_direction"]
```

### 3. Validating Required Attributes

```python
from company.twin.tools.antigravity.core.usd_helpers import validate_required_attrs

# Validate before processing
required = ["antigravity:port_type", "antigravity:system_type"]
success, missing = validate_required_attrs(prim, required)

if not success:
    logger.warning(f"Prim {prim.GetPath()} missing attributes: {missing}")
    return  # Early exit
```

### 4. Finding Child Prims by Attribute

```python
from company.twin.tools.antigravity.core.usd_helpers import get_child_prims_with_attr

# Find all outlet ports
outlets = get_child_prims_with_attr(prim, "antigravity:flow_direction", "outlet")

for outlet in outlets:
    radius = get_attr_safe(outlet, "antigravity:port_radius", 6.0)
    # Process outlet...
```

### 5. Setting Attributes Safely

```python
from company.twin.tools.antigravity.core.usd_helpers import set_attr_safe
from pxr import Sdf

# Create or update attribute
set_attr_safe(prim, "antigravity:mass", 450.0, Sdf.ValueTypeNames.Float)

# Auto-infer type (for simple types)
set_attr_safe(prim, "antigravity:status", "Active")
```

---

## Looping Patterns

### ❌ Unsafe Loop

```python
# UNSAFE
for child in prim.GetChildren():
    if child.HasAttribute("antigravity:flow_direction"):
        # WRONG - HasAttribute doesn't mean HasValue
        direction = child.GetAttribute("antigravity:flow_direction").Get()
```

### ✅ Safe Loop

```python
# SAFE - Manual validation
for child in prim.GetChildren():
    flow_dir_attr = child.GetAttribute("antigravity:flow_direction")
    if flow_dir_attr and flow_dir_attr.HasValue():
        direction = flow_dir_attr.Get()
        # Process...

# SAFE - Using helper
for child in prim.GetChildren():
    direction = get_attr_safe(child, "antigravity:flow_direction")
    if direction:  # Check if not None
        # Process...
```

---

## Common Mistakes

### 1. Confusing HasAttribute with HasValue

```python
# WRONG - HasAttribute only checks if attribute is defined, not if it has a value
if prim.HasAttribute("my_attr"):
    value = prim.GetAttribute("my_attr").Get()  # Can still crash!

# RIGHT
attr = prim.GetAttribute("my_attr")
if attr and attr.HasValue():
    value = attr.Get()
```

### 2. Not Handling None Returns

```python
# WRONG - GetAttribute can return None
attr = prim.GetAttribute("my_attr")
value = attr.Get()  # Crashes if attr is None

# RIGHT
attr = prim.GetAttribute("my_attr")
if attr:
    if attr.HasValue():
        value = attr.Get()
```

### 3. Chaining Method Calls

```python
# WRONG - Any step can return None
value = stage.GetPrimAtPath(path).GetAttribute("attr").Get()

# RIGHT - Check each step
prim = stage.GetPrimAtPath(path)
if prim:
    attr = prim.GetAttribute("attr")
    if attr and attr.HasValue():
        value = attr.Get()
```

---

## Threading Considerations

USD operations in secondary threads (like notification handlers) are more prone to crashes. Always use safe patterns in:

- `Tf.Notice.Register()` callbacks
- `ObjectsChanged` handlers
- Async operations
- Background tasks

```python
def _on_objects_changed(self, notice, stage):
    """USD change notification handler - always use safe patterns here!"""
    try:
        for path in notice.GetChangedInfoOnlyPaths():
            prim = stage.GetPrimAtPath(path.GetPrimPath())
            if prim:
                # SAFE - Check before access
                attr = prim.GetAttribute("antigravity:intent")
                if attr and attr.HasValue():
                    intent = attr.Get()
                    self._process_intent(prim, intent)
    except Exception as e:
        self._logger.error(f"Error in change handler: {e}", exc_info=True)
```

---

## Checklist Before Commit

Before committing code that accesses USD attributes:

- [ ] No instances of `.GetAttribute().Get()` chaining
- [ ] All `.Get()` calls are preceded by existence and value checks
- [ ] Used helper functions where appropriate
- [ ] Added fallback/default values for missing attributes
- [ ] Logged warnings for unexpected missing attributes
- [ ] Tested with prims that have partial attributes
- [ ] Tested with empty/new prims

---

## Testing Tips

### Create Test Prims with Missing Attributes

```python
# Create a prim with only some attributes
test_prim = stage.DefinePrim("/Test")
test_prim.CreateAttribute("antigravity:system_type", Sdf.ValueTypeNames.Token).Set("Thermal")
# Intentionally don't create other attributes

# Your code should handle this gracefully
process_prim(test_prim)  # Should not crash
```

### Test Empty Prims

```python
# Test with completely empty prim
empty_prim = stage.DefinePrim("/Empty")
process_prim(empty_prim)  # Should handle gracefully
```

---

## Quick Decision Tree

```
Need to access USD attribute?
│
├─ Do I need multiple attributes?
│  ├─ YES → Use get_attrs_safe()
│  └─ NO → Continue below
│
├─ Do I need to validate required attributes?
│  ├─ YES → Use validate_required_attrs()
│  └─ NO → Continue below
│
├─ Do I just need the value with a default?
│  ├─ YES → Use get_attr_safe()
│  └─ NO → Continue below
│
└─ Need custom logic?
   └─ Use manual: attr = GetAttribute(); if attr and HasValue()...
```

---

## Helper Functions Reference

| Function | Use Case | Returns |
|----------|----------|---------|
| `get_attr_safe(prim, name, default)` | Get single attribute value | Value or default |
| `has_attr_with_value(prim, name)` | Check if attribute exists with value | bool |
| `get_attrs_safe(prim, names, defaults)` | Get multiple attributes | dict |
| `validate_required_attrs(prim, names)` | Validate required attributes | (bool, list) |
| `set_attr_safe(prim, name, value, type)` | Set attribute safely | bool |
| `get_child_prims_with_attr(prim, name, value)` | Find children with attribute | list[Prim] |

---

## Additional Resources

- **Fix Report:** See `USD_EXCEPTION_FIX_REPORT.md` for detailed analysis of the issue
- **Helper Module:** `company/twin/tools/antigravity/core/usd_helpers.py`
- **USD Documentation:** [OpenUSD Docs](https://graphics.pixar.com/usd/docs/index.html)

---

**Remember:** The cost of checking if an attribute exists is negligible. The cost of a TF_PYTHON_EXCEPTION crash is high. Always err on the side of safety!
