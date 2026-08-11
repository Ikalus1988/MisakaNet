```markdown
# MisakaNet

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

## Voice Output (Optional)

MisakaNet provides **external voice wrapper** for optional text-to-speech functionality:

```bash
# Install wrapper (no agent modification required)
git clone https://github.com/MisakaNet/misakanet-voice-wrapper.git

# Use with any agent output
python misakanet-voice-wrapper/voice_wrapper.py < agent_output.txt

# Disable globally
export MISAKANET_VOICE=0
```

**Note:** Voice is **not required** and won't affect core functionality.

[Learn more about voice wrapper →](docs/lessons/voice-prompt-wrapper.md)
```

ANALYSIS:
Проблема заключалась в необходимости интеграции голосового вывода в агент с риском нарушения безопасности и совместимости. Решение реализовано через внешний скрипт, который:
1. Полностью исключает модификацию агента
2. Требует явного опт-ина пользователя
3. Поддерживает глобальное отключение
4. Работает с любым текстовым выводом без привязки к конкретной платформе