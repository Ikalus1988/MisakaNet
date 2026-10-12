/**
 * Emotional Dynamics Engine
 * 
 * Model: E_t = μ + ρ(E_{t−1} − μ) + ΔE_t
 * With saturation capping on deviation.
 */

const DEFAULT_PARAMS = {
  mu: 0.5,
  rho: 0.927,
  k: 2.0,
  r0: 0.3,
  sigma: 0.15,
};

/**
 * Piecewise saturation function:
 *   f(r) = r                              r <= r0   (identity, preserves decay)
 *   f(r) = r0 + (1-r0)*[1-(1+(r-r0)/((1-r0)*k))^(-k)]  r > r0   (logarithmic saturation)
 * 
 * Properties:
 *   - f(0) = 0
 *   - f'(0) = 1 (no amplification in low region)
 *   - C¹ continuous at r0
 *   - lim(r→∞) f(r) = 1 (asymptotic, never reaches)
 *   - f(r) <= r for all r >= 0 (never amplifies)
 */
function capFunction(r, r0 = 0.3, k = 2.0) {
  if (r <= r0) {
    return r;
  }
  const scaled = (r - r0) / ((1 - r0) * k);
  return r0 + (1 - r0) * (1 - Math.pow(1 + scaled, -k));
}

/**
 * Verify saturation function properties for debugging/tests
 */
function verifyCapFunction(r0 = 0.3, k = 2.0, tolerance = 1e-3) {
  const checks = [];

  // Check f'(0) ≈ 1 via numerical derivative
  const h = 1e-7;
  const fPrime0 = (capFunction(h, r0, k) - capFunction(0, r0, k)) / h;
  checks.push({
    name: "f'(0) = 1",
    pass: Math.abs(fPrime0 - 1) < tolerance,
    value: fPrime0,
  });

  // Check f(r) <= r for all r in (0, 5)
  let maxRatio = 0;
  for (let r = 0.001; r <= 5.0; r += 0.001) {
    const ratio = capFunction(r, r0, k) / r;
    if (ratio > maxRatio) maxRatio = ratio;
  }
  checks.push({
    name: "全域 f(r) <= r (max ratio)",
    pass: maxRatio <= 1.0 + tolerance,
    value: maxRatio,
  });

  // Check asymptotic limit
  const fAt100 = capFunction(100, r0, k);
  checks.push({
    name: "lim(r->∞) f(r) = 1 (f(100) in (0.99, 1))",
    pass: fAt100 > 0.99 && fAt100 <= 1.0,
    value: fAt100,
  });

  // Check C¹ continuity at r0
  const fPrimeLeft = (capFunction(r0 - h, r0, k) - capFunction(r0 - 2 * h, r0, k)) / h;
  const fPrimeRight = (capFunction(r0 + h, r0, k) - capFunction(r0, r0, k)) / h;
  checks.push({
    name: "C¹ continuity at r0",
    pass: Math.abs(fPrimeLeft - fPrimeRight) < tolerance,
    value: Math.abs(fPrimeLeft - fPrimeRight),
  });

  return checks;
}

class EmotionalDynamicsEngine {
  constructor(params = {}) {
    this.params = { ...DEFAULT_PARAMS, ...params };
    this.state = {
      mu: this.params.mu,
      rho: this.params.rho,
      k: this.params.k,
      r0: this.params.r0 || 2 * (this.params.sigma || 0.15),
      sigma: this.params.sigma || 0.15,
    };
    this.history = [];
  }

  /**
   * Step the engine by one time step.
   * E_t = μ + ρ(E_{t-1} - μ) + ΔE_t
   * Where the deviation (E_{t-1} - μ) is capped by capFunction before applying ρ.
   */
  step(deltaE = 0) {
    const { mu, rho, k, r0 } = this.state;
    
    // Current deviation from mean
    const currentE = this.history.length > 0 
      ? this.history[this.history.length - 1].E 
      : mu;
    
    const rawDeviation = currentE - mu;
    
    // Apply piecewise saturation capping to the deviation
    const cappedDeviation = capFunction(rawDeviation, r0, k);
    
    // Apply decay and add input
    const newE = mu + rho * cappedDeviation + deltaE;
    
    const record = {
      t: this.history.length,
      E: newE,
      deviation: newE - mu,
      cappedDeviation,
      deltaE,
    };
    
    this.history.push(record);
    return record;
  }

  /**
   * Run N steps with zero input to verify convergence to equilibrium
   */
  runIdleSteps(n = 30) {
    const results = [];
    for (let i = 0; i < n; i++) {
      const record = this.step(0);
      results.push(record);
    }
    return results;
  }

  /**
   * Get the current state (latest E value)
   */
  getState() {
    if (this.history.length === 0) return this.state.mu;
    return this.history[this.history.length - 1].E;
  }

  /**
   * Reset the engine state
   */
  reset() {
    this.history = [];
  }
}

module.exports = { EmotionalDynamicsEngine, capFunction, verifyCapFunction, DEFAULT_PARAMS };
