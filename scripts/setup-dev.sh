#!/bin/bash

# Установка pre-commit
pip install pre-commit

# Установка хуков
pre-commit install

# Установка lesson-lint (если не установлен)
pip install -e .

echo "Pre-commit hooks installed successfully!"