/**
 * Regression tests for the saturation function fix.
 * 
 * Verifies:
 * ① f'(0) = 1 (low region doesn't amplify)
 * ② Global f(r) <= r (never amplifies anywhere)
 * ③ lim(r→∞) f(r) = 1
 * ④ C¹ continuity at r0
 * ⑤ Idle N-step convergence to 0 deviation from multiple starting points
 */

const { capFunction, verifyCapFunction, EmotionalDynamicsEngine } = require("../src/engine");

const TESTS = [];
let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (condition) {
    passed++;
    TESTS.push({ name: message, status: "PASS" });
    console.log(`  ✓ ${message}`);
  } else {
    failed++;
    TESTS.push({ name: message, status: "FAIL" });
    console.log(`  ✗ ${message}`);
  }
}

console.log("=== Saturation Function Regression Tests ===\n");

// Test 1: f'(0) = 1
console.log("① f'(0) = 1 (numerical derivative check)");
const derivChecks = verifyCapFunction();
for (const check of derivChecks) {
  assert(check.pass, `${check.name}: ${check.value.toFixed(6)}`);
}

// Test 2: Global f(r) <= r
console.log("\n② Global f(r) <= r (scan r in (0, 5])");
const k = 2.0;
const r0 = 0.3;
let maxRatio = 0;
for (let r = 0.001; r <= 5.0; r += 0.001) {
  const ratio = capFunction(r, r0, k) / r;
  if (ratio > maxRatio) maxRatio = ratio;
}
assert(maxRatio <= 1.001, `max f(r)/r = ${maxRatio.toFixed(6)} (should be ≤ 1)`);

// Test 3: Asymptotic limit
console.log("\n③ lim(r→∞) f(r) = 1");
const fAt100 = capFunction(100, r0, k);
assert(fAt100 > 0.99 && fAt100 <= 1.0, `f(100) = ${fAt100.toFixed(6)} (should be in (0.99, 1))`);

// Test 4: C¹ continuity at r0
console.log("\n④ C¹ continuity at r0");
const h = 1e-7;
const fPrimeLeft = (capFunction(r0 - h, r0, k) - capFunction(r0 - 2 * h, r0, k)) / h;
const fPrimeRight = (capFunction(r0 + h, r0, k) - capFunction(r0, r0, k)) / h;
assert(Math.abs(fPrimeLeft - fPrimeRight) < 1e-3, 
  `derivative discontinuity = ${Math.abs(fPrimeLeft - fPrimeRight).toExponential(4)} (should be < 1e-3)`);

// Test 5: Idle convergence from multiple starting points
console.log("\n⑤ Idle N-step convergence (zero input, 30 steps)");
const startPoints = [0.01, 0.05, 0.15, 0.30, 0.60];
const rho = 0.927;
let allConverged = true;

for (const r of startPoints) {
  const engine = new EmotionalDynamicsEngine({
    mu: 0.5,
    rho: rho,
    k: k,
    r0: r0,
  });
  // Seed with initial deviation
  engine.reset();
  // Manually set history to simulate starting from deviation r
  const mu = 0.5;
  engine.history = [{ t: -1, E: mu + r, deviation: r, cappedDeviation: capFunction(r, r0, k), deltaE: 0 }];
  
  const results = engine.runIdleSteps(30);
  const finalDeviation = results[results.length - 1].deviation;
  
  // Should decay toward 0, not converge to a non-zero equilibrium
  assert(finalDeviation < r * 0.15, 
    `r0=${r}: final deviation = ${finalDeviation.toFixed(6)} (should decay, was ${r})`);
  
  if (finalDeviation >= r * 0.15) allConverged = false;
}

// Test 6: Verify the old broken function would fail
console.log("\n⑥ Old broken function comparison (should show amplification)");
const oldCapFunction = (r) => 1 - Math.pow(1 + r, -k);
const oldRatios = [0.001, 0.01, 0.1, 0.5, 0.73, 1.0].map(r => ({
  r,
  ratio: oldCapFunction(r) / r,
}));
// Show that old function amplifies at low r (for information only)
console.log("   Old function f(r)/r ratios:");
for (const { r, ratio } of oldRatios) {
  console.log(`     r=${r}: f(r)/r = ${ratio.toFixed(4)} ${ratio > 1 ? "← AMPLIFIES" : "← compresses"}`);
}
assert(oldRatios[0].ratio > 1, "Old function amplifies at low r (confirmed bug)");

// Summary
console.log(`\n=== Results: ${passed} passed, ${failed} failed out of ${passed + failed} tests ===`);

if (failed > 0) {
  process.exit(1);
}
