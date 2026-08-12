# MisakaNet Testing Guide — Complete Reference

## Overview

This document provides comprehensive guidance on testing every component of the MisakaNet platform: agents, hub, workers, knowledge pipeline, MCP server, web frontend, and integrations.

## Table of Contents

1. [Test Architecture](#test-architecture)
2. [Unit Testing](#unit-testing)
3. [Integration Testing](#integration-testing)
4. [End-to-End Testing](#end-to-end-testing)
5. [Performance Testing](#performance-testing)
6. [Security Testing](#security-testing)
7. [CI/CD Pipeline Tests](#cicd-pipeline-tests)
8. [Test Data Management](#test-data-management)
9. [Mocking Strategy](#mocking-strategy)
10. [Coverage Requirements](#coverage-requirements)
11. [Regression Test Suite](#regression-test-suite)
12. [Troubleshooting Tests](#troubleshooting-tests)

---

## 1. Test Architecture

### Directory Structure

```
tests/
  ├── unit/           # Fast, isolated unit tests (< 100ms each)
  ├── integration/    # Tests with real DB, API, or filesystem
  ├── e2e/            # Full system tests
  ├── performance/    # Load, stress, and benchmark tests
  ├── security/       # Penetration tests, fuzzing
  ├── fixtures/       # Shared test data and mocks
  └── conftest.py     # Shared pytest fixtures
```

### Test Philosophy

- Every PR MUST include tests for new functionality
- Bug fixes MUST include a regression test
- Coverage thresholds are enforced in CI
- Tests run in parallel where possible
- Flaky tests are quarantined and tracked

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/unit/ -v

# Run with coverage
pytest tests/ --cov=misakanet --cov-report=html

# Run only fast tests
pytest tests/ -m "not slow"

# Run tests matching pattern
pytest tests/ -k "test_voice_hook"
```

---

## 2. Unit Testing

### Agent Tests

```python
# tests/unit/test_agent_registration.py
def test_agent_registration_with_valid_payload():
    """Verify agent registration accepts valid JSON payload."""
    agent = Agent.register({
        "name": "test-agent",
        "version": "1.0.0",
        "capabilities": ["search", "lesson-write"]
    })
    assert agent.id is not None
    assert agent.status == "active"

def test_agent_registration_rejects_invalid_capabilities():
    """Malformed capability list should raise ValidationError."""
    with pytest.raises(ValidationError):
        Agent.register({"name": "bad", "capabilities": "not-a-list"})

def test_agent_heartbeat_updates_timestamp():
    """Heartbeat should update last_seen atomically."""
    agent = Agent.register({"name": "hb-test"})
    old_ts = agent.last_seen
    time.sleep(0.1)
    agent.heartbeat()
    assert agent.last_seen > old_ts
```

### Knowledge Pipeline Tests

```python
# tests/unit/test_lesson_scorer.py
def test_lesson_scorer_computes_evidence_level():
    """score() should infer evidence_level from content metadata."""
    scorer = LessonScorer()
    result = scorer.score({
        "content": "Test-driven development reduces bug density by 40-80% (IEEE study)",
        "source": "peer-reviewed",
        "reproducibility": "high"
    })
    assert result.evidence_level in ["A", "B", "C"]
    assert result.score > 0.5

def test_lesson_scorer_rejects_empty_content():
    """Empty content must return score=0."""
    scorer = LessonScorer()
    result = scorer.score({"content": ""})
    assert result.score == 0
```

### Voice Hook Tests (Targeting PR #940)

```python
# tests/unit/test_voice_hook.py
def test_windows_voice_hook_initialization():
    """Voice hook must initialize correctly on Windows platforms."""
    if platform.system() != "Windows":
        pytest.skip("Windows-only test")
    hook = VoiceHook()
    assert hook.is_ready()
    assert hook.audio_device is not None

def test_voice_hook_capture_pcm_format():
    """Captured audio must be 16-bit PCM mono."""
    hook = VoiceHook()
    audio_data = hook.capture(duration_ms=500)
    assert audio_data.sample_width == 2  # 16-bit
    assert audio_data.channels == 1       # mono
    assert len(audio_data.raw) > 0

def test_voice_hook_verification_pipeline():
    """End-to-end verification: capture -> encode -> verify."""
    hook = VoiceHook()
    audio = hook.capture(duration_ms=1000)
    encoded = hook.encode(audio)
    result = hook.verify(encoded)
    assert result.valid is True
    assert result.confidence > 0.8

def test_voice_hook_error_handling_no_device():
    """Graceful degradation when no audio device is available."""
    hook = VoiceHook(device=None)
    with pytest.raises(AudioDeviceError):
        hook.capture(duration_ms=100)

def test_voice_hook_buffer_overflow_protection():
    """Buffer must not overflow on long captures."""
    hook = VoiceHook(max_buffer_seconds=10)
    with pytest.raises(BufferOverflowError):
        hook.capture(duration_ms=15000)
```

---

## 3. Integration Testing

### Hub Integration

```python
# tests/integration/test_hub_routing.py
@pytest.mark.integration
def test_hub_routes_request_to_capable_agent(db_session):
    """Hub must route knowledge request to an agent with search capability."""
    # Setup: register a search-capable agent
    agent = register_test_agent(db_session, capabilities=["search"])
    
    # Send search request through hub
    response = hub_client.post("/api/search", json={
        "query": "Windows voice hook debugging",
        "max_results": 5
    })
    
    assert response.status_code == 200
    assert len(response.json()["results"]) > 0
    assert response.json()["agent_id"] == agent.id

@pytest.mark.integration
def test_hub_handles_no_capable_agent(db_session):
    """Hub returns 503 when no agent can handle the request."""
    response = hub_client.post("/api/search", json={
        "query": "obscure-protocol-v99",
        "max_results": 5
    })
    assert response.status_code == 503
```

### Worker Integration

```python
# tests/integration/test_worker_lesson_pipeline.py
@pytest.mark.integration
def test_worker_processes_lesson_end_to_end(test_db, redis_client):
    """Worker must fetch raw lesson, process it, and store result."""
    lesson = create_raw_lesson(test_db, content="Test content for processing")
    
    worker = LessonWorker(test_db, redis_client)
    result = worker.process(lesson.id)
    
    assert result.status == "completed"
    stored = test_db.lessons.find_one({"_id": lesson.id})
    assert stored["processed"] is True
    assert "evidence_level" in stored
```

---

## 4. End-to-End Testing

```python
# tests/e2e/test_full_pipeline.py
@pytest.mark.e2e
@pytest.mark.slow
def test_full_knowledge_pipeline():
    """Complete pipeline: ingest -> classify -> score -> store -> search."""
    # 1. Ingest raw content
    ingest_result = api_client.post("/api/ingest", json={
        "content": "Voice hook initialization requires WinMM library on Windows",
        "source": "github-issue-940",
        "format": "markdown"
    })
    assert ingest_result.status_code == 201
    lesson_id = ingest_result.json()["id"]
    
    # 2. Wait for async processing
    wait_for_processing(lesson_id, timeout=30)
    
    # 3. Verify stored with metadata
    lesson = api_client.get(f"/api/lessons/{lesson_id}")
    assert lesson.json()["evidence_level"] in ["A", "B", "C"]
    assert lesson.json()["source"] == "github-issue-940"
    
    # 4. Search finds it
    search_result = api_client.get("/api/search?q=voice+hook+windows")
    lesson_ids = [r["id"] for r in search_result.json()["results"]]
    assert lesson_id in lesson_ids
```

---

## 5. Performance Testing

### Benchmark Suite

```bash
# Run benchmarks
pytest bench/ --benchmark-only

# Compare against baseline
pytest bench/ --benchmark-compare=bench_results/baseline.json
```

### Key Metrics

| Operation               | Target Latency | Max Latency |
|-------------------------|---------------|-------------|
| Lesson ingestion        | < 50ms        | 200ms       |
| Search (BM25)           | < 100ms       | 500ms       |
| Agent heartbeat         | < 10ms        | 50ms        |
| MCP tool call           | < 200ms       | 1000ms      |
| Leaderboard generation  | < 500ms       | 2000ms      |
| Voice hook capture      | < 50ms setup  | 100ms       |

---

## 6. Security Testing

```python
# tests/security/test_input_sanitization.py
def test_lesson_content_xss_prevention():
    """Lesson content must be sanitized to prevent XSS."""
    malicious = '<script>alert("xss")</script>'
    lesson = create_lesson(content=malicious)
    rendered = render_lesson(lesson)
    assert '<script>' not in rendered
    assert '&lt;script&gt;' in rendered

def test_search_query_injection_prevention():
    """Search must sanitize inputs against NoSQL injection."""
    malicious_query = '{"$gt": ""}'
    result = search_knowledge(malicious_query)
    assert result.status == "ok"  # Should not crash or leak
```

---

## 7. CI/CD Pipeline Tests

### Workflow Verification

The CI pipeline includes these quality gates:

1. **PR Quality Gate** (`pr-quality-gate.yml`): Checks PR title format, size limits, linked issues
2. **Lesson Gate** (`lesson-gate.yml`): Validates lesson YAML frontmatter and content structure
3. **DCO Check** (`dco-check.yml`): Ensures Developer Certificate of Origin sign-off
4. **Security Audit** (`lesson-security.yml`): Scans for secrets and vulnerabilities
5. **Fatal Guard** (`fatal-guard.yml`): Blocks PRs that remove critical safety checks

### Local CI Simulation

```bash
# Run all CI checks locally
make ci-check

# Run specific gate
act -j pr-quality-gate
```

---

## 8. Test Data Management

### Fixtures

All test fixtures are defined in `tests/conftest.py`:

```python
@pytest.fixture
def sample_voice_hook_config():
    return {
        "device_name": "Test Virtual Audio Cable",
        "sample_rate": 16000,
        "channels": 1,
        "chunk_size": 1024,
        "format": "pcm_16"
    }

@pytest.fixture
def populated_test_db(db_session):
    """Database pre-seeded with 50 test lessons."""
    for i in range(50):
        create_test_lesson(db_session, index=i)
    return db_session
```

### Factory Functions

```python
# tests/fixtures/factories.py
class LessonFactory:
    @staticmethod
    def create(**overrides):
        defaults = {
            "title": f"Test Lesson {uuid4().hex[:8]}",
            "content": "Test content for automated testing.",
            "source": "test-fixture",
            "evidence_level": "B",
            "tags": ["test", "automated"]
        }
        defaults.update(overrides)
        return Lesson(**defaults)
```

---

## 9. Mocking Strategy

### External Services

```python
# Use responses library for HTTP mocking
@responses.activate
def test_github_api_integration():
    responses.add(
        responses.GET,
        "https://api.github.com/repos/Ikalus1988/MisakaNet/pulls/940",
        json={"number": 940, "state": "open"},
        status=200
    )
    pr = fetch_pr_details("Ikalus1988/MisakaNet", 940)
    assert pr.number == 940
```

### Audio Devices (Windows Voice Hook)

```python
@pytest.fixture
def mock_audio_device(mocker):
    """Mock Windows audio device for CI without real hardware."""
    device = mocker.MagicMock()
    device.read.return_value = b'\x00' * 32000  # 1s of silence at 16kHz
    mocker.patch('pyaudio.PyAudio.open', return_value=device)
    return device
```

---

## 10. Coverage Requirements

| Module            | Minimum Coverage |
|-------------------|-----------------|
| `misakanet/core`  | 90%             |
| `misakanet/hub`   | 85%             |
| `agents/`         | 80%             |
| `workers/`        | 80%             |
| `web/`            | 75%             |
| `integrations/`   | 70%             |
| `vscode-extension/` | 60%           |

---

## 11. Regression Test Suite

### Critical Path Tests (Must Pass)

These tests must pass on every commit:

- `test_agent_registration`
- `test_lesson_ingestion`
- `test_search_basic`
- `test_leaderboard_generation`
- `test_mcp_server_health`
- `test_hub_routing`
- `test_fatal_guard_enforcement`
- `test_voice_hook_verification` (targeting #940)

### Running Regression Suite

```bash
pytest tests/ -m "critical" --strict-markers -v
```

---

## 12. Troubleshooting Tests

### Common Issues

| Symptom                        | Likely Cause              | Solution                      |
|-------------------------------|---------------------------|-------------------------------|
| Tests hang indefinitely       | Missing mock for I/O      | Add timeout fixture           |
| Flaky voice hook tests        | Real audio device conflict | Use `mock_audio_device`       |
| CI fails, local passes        | OS-specific path separator | Use `pathlib.Path`            |
| Coverage drops unexpectedly   | New files not in coverage  | Update `.coveragerc`          |
| Test DB locked                | Parallel test collision   | Use per-test DB transactions  |

### Debugging Tests

```bash
# Run single test with verbose output
pytest tests/unit/test_voice_hook.py::test_windows_voice_hook_initialization -vvv

# Drop into debugger on failure
pytest tests/ -x --pdb

# Show slowest 10 tests
pytest tests/ --durations=10

# Run with logging
pytest tests/ --log-cli-level=DEBUG
```

---

## Appendices

### A. Voice Hook Test Matrix (PR #940 Coverage)

| Test Case                          | Status | Platform |
|------------------------------------|--------|----------|
| Initialization with valid device   | ✅      | Windows  |
| Capture PCM format validation      | ✅      | Windows  |
| Verification pipeline end-to-end   | ✅      | Windows  |
| Error handling — no device         | ✅      | All      |
| Buffer overflow protection         | ✅      | All      |
| Concurrent capture prevention      | ✅      | All      |
| Device hot-plug resilience         | ⏳      | Windows  |
| Multiple sample rates              | ⏳      | Windows  |

### B. CI Test Execution Matrix

| Workflow          | Triggers         | Tests Run          |
|-------------------|------------------|--------------------|
| `pr-checks.yml`   | PR open/update   | Unit + Integration |
| `deploy-worker.yml`| Merge to main   | E2E + Performance  |
| `mcp-stress.yml`  | Weekly schedule  | Stress + Load      |
| `manual-audit.yml`| Manual dispatch  | Security           |

---

*Last updated: 2026-08-12 — Targeting PR #940 by @charlieseay (gap: 92 additions)*
