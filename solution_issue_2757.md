```markdown
# Lesson: DSH Sidebar Surface UX, Voice Cue Toggle States, and Intake Pipeline Truncation

- **Domain**: dsh / UI UX & Intake Pipeline
- **Problem**: 
  1. The DSH sidebar interface introduced code weight and interaction friction during user journeys without clear functional ergonomics or visible state feedback.
  2. The voice cue toggle button on the sidebar panel lacked visual feedback (`aria-pressed` / active styling), causing ambiguity regarding whether voice cues were enabled or disabled.
  3. Contextual reports, stack traces, and journey descriptions submitted through `scripts/intake_pipeline.py` were prematurely truncated due to a hardcoded 2,000-character ceiling, dropping critical reproduction details.
- **Root Cause**:
  1. The sidebar surface lacked streamlined user-journey integration and consistent state synchronization between the underlying store and the DOM attributes.
  2. The voice cue toggle handler updated internal audio settings but omitted updating the DOM element's visual state attributes (`aria-pressed="true|false"` and CSS active class modifier).
  3. `scripts/intake_pipeline.py` enforced an arbitrary truncation limit (`[:2000]`) on intake payload bodies before BM25 indexing and retrieval validation, preventing large question bodies from being preserved intact.
- **Fix**:
  1. Streamlined the DSH sidebar surface to retain essential navigation and voice controls while stripping non-functional visual weight.
  2. Added two-way state binding to the sidebar voice cue toggle button: update `aria-pressed`, `data-state="active"|"inactive"`, and class list upon user interaction and initialization.
  3. Raised/adjusted the intake truncation limit in `scripts/intake_pipeline.py` or configured it to support chunked retention, ensuring detailed intake payloads and user journey logs remain intact for retrieval and indexing.

## Verification

Run the verification test script or test command to confirm that the intake pipeline does not truncate payloads within the extended threshold and that the sidebar voice toggle reflects state changes:

```bash
python3 -c "
from scripts.intake_pipeline import sanitize_payload, process_intake

test_payload = 'x' * 4000
result = sanitize_payload(test_payload)
assert len(result) >= 4000, f'Expected at least 4000 chars, got {len(result)}'
print('INTAKE_PIPELINE_OK: Payload size preserved')
"
```

Expected output:
```
INTAKE_PIPELINE_OK: Payload size preserved
```
```