"""
Regression tests for the saturation function fix.
Port of demo/test-regression.js to Python for cross-validation.
"""

import math


def cap_function(r, r0=0.3, k=2.0):
    """Piecewise saturation function."""
    if r <= r0:
        return r
    scaled = (r - r0) / ((1 - r0) * k)
    return r0 + (1 - r0) * (1 - (1 + scaled) ** (-k))


def old_cap_function(r, k=2.0):
    """Old broken saturation function."""
    return 1 - (1 + r) ** (-k)


def test_deriv_zero():
    """f'(0) should equal 1."""
    h = 1e-7
    f_prime = (cap_function(h) - cap_function(0)) / h
    assert abs(f_prime - 1) < 1e-3, f"f'(0) = {f_prime:.6f}, expected 1"
    print(f"  ✓ f'(0) = {f_prime:.6f}")


def test_global_no_amplify():
    """f(r) <= r for all r in (0, 5]."""
    max_ratio = 0
    for i in range(1, 5001):
        r = i * 0.001
        ratio = cap_function(r) / r
        if ratio > max_ratio:
            max_ratio = ratio
    assert max_ratio <= 1.001, f"max f(r)/r = {max_ratio:.6f}"
    print(f"  ✓ max f(r)/r = {max_ratio:.6f}")


def test_asymptotic_limit():
    """lim(r→∞) f(r) = 1."""
    f100 = cap_function(100)
    assert 0.99 < f100 <= 1.0, f"f(100) = {f100:.6f}"
    print(f"  ✓ f(100) = {f100:.6f}")


def test_c1_continuity():
    """C¹ continuity at r0."""
    r0 = 0.3
    h = 1e-7
    f_prime_left = (cap_function(r0 - h) - cap_function(r0 - 2 * h)) / h
    f_prime_right = (cap_function(r0 + h) - cap_function(r0)) / h
    discontinuity = abs(f_prime_left - f_prime_right)
    assert discontinuity < 1e-3, f"derivative discontinuity = {discontinuity:.2e}"
    print(f"  ✓ C¹ continuity at r0: discontinuity = {discontinuity:.2e}")


def test_idle_convergence():
    """Zero input: deviation should decay to 0 from multiple starts."""
    rho = 0.927
    r0 = 0.3
    start_points = [0.01, 0.05, 0.15, 0.30, 0.60]
    
    for r in start_points:
        deviation = r
        for _ in range(30):
            capped = cap_function(deviation, r0)
            deviation = rho * capped
        assert deviation < r * 0.15, f"r0={r}: final dev = {deviation:.6f}"
        print(f"  ✓ r0={r}: final deviation = {deviation:.6f}")


def test_old_function_bug():
    """Demonstrate the old function amplifies at low r."""
    ratios = []
    for r in [0.001, 0.01, 0.1, 0.5, 0.73, 1.0]:
        ratio = old_cap_function(r) / r
        ratios.append((r, ratio))
        mark = "← AMPLIFIES" if ratio > 1 else "← compresses"
        print(f"     r={r}: f(r)/r = {ratio:.4f} {mark}")
    assert ratios[0][1] > 1, "Old function amplifies at low r"


if __name__ == "__main__":
    print("=== Saturation Function Regression Tests (Python) ===\n")
    test_deriv_zero()
    test_global_no_amplify()
    test_asymptotic_limit()
    test_c1_continuity()
    test_idle_convergence()
    print("\n⑥ Old broken function comparison:")
    test_old_function_bug()
    print("\n=== All tests passed ===")
