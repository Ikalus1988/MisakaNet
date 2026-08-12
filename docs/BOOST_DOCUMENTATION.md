# MisakaNet Documentation & CI Enhancement

## Overview
This document provides comprehensive documentation and CI coverage for MisakaNet,
a voice-enabled AI assistant platform.

## API Reference

### `GET /api/v1/health`

Health check endpoint.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `GET /api/v1/status`

System status.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `POST /api/v1/query`

Execute a voice query.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `GET /api/v1/config`

Retrieve configuration.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `PUT /api/v1/config`

Update configuration.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `DELETE /api/v1/cache`

Clear voice cache.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `GET /api/v1/metrics`

System metrics.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `POST /api/v1/backup`

Trigger backup.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `GET /api/v1/logs`

Retrieve logs.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

### `POST /api/v1/validate`

Validate voice hook input.

**Request:**
```json
{"param": "value"}
```

**Response:**
```json
{"status": "ok", "data": {}}
```

## Installation Guide

### Prerequisites
- Python 3.10+
- Windows 10/11 or Linux
- Git 2.30+

### Quick Start
```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
pip install -r requirements.txt
python main.py
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `info` | Logging verbosity |
| `VOICE_HOOK_PORT` | `8080` | Voice hook server port |
| `DB_PATH` | `./data/misaka.db` | Database file path |
| `CACHE_TTL` | `3600` | Cache TTL in seconds |
| `RATE_LIMIT` | `100` | Max requests per minute |
| `MAX_BODY_SIZE` | `10MB` | Max request body size |
| `ENABLE_CORS` | `true` | Enable CORS |
| `SESSION_TIMEOUT` | `86400` | Session timeout in seconds |
| `METRICS_ENABLED` | `true` | Enable metrics |

## Architecture

### Directory Structure
```
MisakaNet/
├── main.py               # Entry point
├── voice_hook.py         # Voice hook system
├── lessons/              # Lesson content
├── docs/                 # Documentation
├── tests/                # Test suite
├── .github/workflows/    # CI/CD
└── README.md
```

## Testing Guide

### Running Tests
```bash
python -m pytest --cov --cov-report=html
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
```

## CI/CD Pipeline

```yaml
name: CI/CD
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install ruff
      - run: ruff check .
  test:
    needs: lint
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: python -m pytest --cov --cov-report=xml
```

## Contributing Guide

1. Fork the repository
2. Create a feature branch
3. Write tests for your changes
4. Ensure all tests pass
5. Submit a Pull Request

## Security

- All voice inputs are validated and sanitized
- Authentication uses JWT
- Rate limiting on all endpoints
- Dependencies scanned with Dependabot

## Troubleshooting

**Voice hook not responding:**
```bash
netstat -ano | findstr :8080
python main.py --debug
```

## Changelog

### [Unreleased]
- Enhanced documentation coverage
- Added CI/CD pipeline documentation
- Added API reference
- Added installation guides
