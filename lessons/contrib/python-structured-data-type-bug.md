{
  "title": "Python: AttributeError on List When Dict Expected — Structured Data Type Mismatch",
  "domain": "python",
  "tags": ["python", "type-error", "data-structures", "web-scraping", "json"],
  "status": "published",
  "source": "hanyuanchen08-netizen"
}

# Python: AttributeError on List When Dict Expected

## Problem

While building a universal web scraper, calling `result["structured_data"]["prices"].append(price)` failed with:

```
AttributeError: 'list' object has no attribute 'get'
```

The variable `result["structured_data"]` was initialized as `[]` (an empty list) but later accessed as a dictionary with `result["structured_data"]["prices"]`.

```python
# Buggy code
result = {"structured_data": []}  # ← LIST, not dict!

def extract_prices(html):
    price = parse_price(html)
    result["structured_data"]["prices"].append(price)  # ← BOOM
```

## Root Cause

**Initialization mismatch**: The `structured_data` variable was initialized as a list early in the function (intended as a fallback container), but downstream code treated it as a nested dictionary with string keys. Python silently allowed the first access through because the variable name overlay hid the type change until the runtime attribute lookup failed.

This is a common pattern when:
1. Scraping multiple pages and accumulating results
2. Refactoring a flat structure to a nested one without updating the initializer
3. Using the same variable name for different-purpose accumulators

## Fix

### Option A: Fix the initializer (preferred)
```python
# Correct initialization
result = {"structured_data": {}}  # ← DICT

def extract_prices(html):
    if "prices" not in result["structured_data"]:
        result["structured_data"]["prices"] = []
    price = parse_price(html)
    result["structured_data"]["prices"].append(price)
```

### Option B: Use defaultdict for safety
```python
from collections import defaultdict

result = {"structured_data": defaultdict(list)}

def extract_prices(html):
    price = parse_price(html)
    result["structured_data"]["prices"].append(price)  # defaultdict handles missing keys
```

### Option C: Add a type guard
```python
def extract_prices(html):
    if not isinstance(result.get("structured_data"), dict):
        result["structured_data"] = {}
    result["structured_data"].setdefault("prices", []).append(parse_price(html))
```

## Verification

```python
# Test with empty case
result = {"structured_data": {}}
extract_prices("<html>...$29.99...</html>")
assert result["structured_data"]["prices"] == [29.99]

# Test with existing prices
extract_prices("<html>...$39.99...</html>")
assert result["structured_data"]["prices"] == [29.99, 39.99]

# Test with no price found
extract_prices("<html>no prices here</html>")
# Should not crash

print("✅ All tests passed")
```

## Key Takeaways

- When a variable is used as both a list and a dict in different code paths, the initializer must match the **most demanding** access pattern (dict before list, not the other way around)
- `dict.setdefault(key, default)` is safer than `dict[key] = default` for initialization
- A type annotation can catch this at lint time: `result: dict[str, dict[str, list]] = {"structured_data": {}}`
- The bug survived initial testing because the first page happened to not trigger the list access path
