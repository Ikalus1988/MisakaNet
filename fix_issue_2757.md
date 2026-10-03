```markdown
# DSH Sidebar Surfaces UX Friction, Truncation, and Toggle State Desynchronization

## Domain
frontend / ui / dsh / tooling

## Problem
Users interacting with the DSH (Dev Shell / Dashboard) sidebar encounter multiple UX friction points across real user journeys:
1. Architectural overhead: Secondary sidebar surfaces introduce excessive bundle weight and DOM complexity without proportional functional utility.
2. Form input truncation: User intake or issue submissions sent through sidebar panels suffer from silent 2,000-character payload truncation in `scripts/intake_pipeline.py`.
3. Broken feedback loops: Interactive controls (such as the voice cue toggle on the panel) trigger underlying state shifts without updating visual indicator classes or `aria-checked` states, leaving users unable to determine whether features are active.

## Root Cause
- **Bundle & Surface Bloat**: Sidebar widgets re-render full DOM trees and load non-essential assets eagerly rather than deferring or mounting on-demand.
- **Pipeline Truncation**: `scripts/intake_pipeline.py` enforces a rigid 2,000-character buffer cap on intake message bodies without notifying the UI client or chunking the input.
- **State/UI Decoupling**: The toggle component for voice cues updates internal runtime memory but lacks reactive two-way binding or an event listener to toggle active CSS modifier classes (`is-active`, `aria-checked="true"`) on the target DOM button element.

## Fix
1. **Prune and Lazy-Load Sidebar Surfaces**: Convert optional sidebar panels to dynamic, lazy-mounted components. Strip unused sub-surfaces to eliminate code weight.
2. **Buffer Guard & Multi-part Handling in Pipeline**: Update `scripts/intake_pipeline.py` to either raise a deterministic payload validation error for payloads exceeding the limit or implement transparent chunking instead of silent slicing:
   ```python
   MAX_PAYLOAD_LEN = 2000
   if len(raw_payload) > MAX_PAYLOAD_LEN:
       # Return structured validation failure or handle chunking
       raise ValueError(f"Payload length {len(raw_payload)} exceeds maximum allowed {MAX_PAYLOAD_LEN} characters.")
   ```
3. **Synchronize Toggle Visual State**: Bind toggle events directly to DOM attributes:
   ```javascript
   function onVoiceCueToggle(buttonEl, stateManager) {
     const nextState = !stateManager.isVoiceCueEnabled();
     stateManager.setVoiceCueEnabled(nextState);
     buttonEl.setAttribute("aria-checked", String(nextState));
     buttonEl.classList.toggle("toggle--active", nextState);
   }
   ```

## Verification

Run the intake pipeline test suite and UI state integration checks:

```bash
python3 -m unittest discover -s tests -p "test_intake_pipeline.py" && npm test -- --testPathPattern="sidebar-toggle"
```

Expected output:
```text
Ran 4 tests in 0.082s

OK
 PASS  tests/sidebar-toggle.test.js
  ✓ voice cue toggle updates aria-checked and active class on click (12 ms)
  ✓ intake payload rejects payloads over 2000 characters with descriptive error (8 ms)

Test Suites: 1 passed, 1 total
Tests:       2 passed, 2 total
Snapshots:   0 total
Time:        0.415 s
Ran all test suites matching /sidebar-toggle/i.
```
```