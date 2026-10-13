---
domain: "python"
title: "Migrate root validator to model validator mode wrap in Pydantic v2"
tags:
  - "pydantic"
  - "pydantic-v2"
  - "validation"
  - "migration"
status: "published"
evidence_level: "E1"
summary_plain: "Pydantic v2 废弃了 root_validator，应改用 model_validator(mode='before' 或 'after')。"
trigger: "PydanticUserWarning: Pydantic V1 style `@root_validator` validators are deprecated and will be removed in V3"
verify: "python -c 'from pydantic import BaseModel, model_validator; print(BaseModel)' 退出码为 0"
---

# Migrate root validator to model validator mode wrap in Pydantic v2

## Problem

Upgrading to Pydantic v2 emits deprecation warnings or raises runtime errors when legacy `@root_validator` decorators are used:
```text
PydanticUserWarning: Pydantic V1 style `@root_validator` validators are deprecated
```

## Root Cause

Pydantic v2 reorganized validation pipelines into explicit modes: `mode='before'` for raw input dictionaries, and `mode='after'` for validated instance fields.

## Solution

Replace `@root_validator` with `@model_validator`:

```python
from pydantic import BaseModel, model_validator

class UserProfile(BaseModel):
    username: str
    email: str

    @model_validator(mode="before")
    @classmethod
    def pre_validate(cls, data: dict):
        if isinstance(data, dict) and "mail" in data:
            data["email"] = data.pop("mail")
        return data
```

## Verification

Run schema validation tests under Pydantic v2:
```bash
python -c "from pydantic import BaseModel, model_validator; print('Pydantic v2 validated')"
```

