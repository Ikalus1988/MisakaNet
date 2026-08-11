```python
#!/usr/bin/env python3
"""
MisakaNet Voice Wrapper - External Opt-In Solution
Usage: python voice_wrapper.py < input.txt
or: cat agent_output.txt | python voice_wrapper.py
"""

import os
import sys
import subprocess
from typing import Optional

class VoiceWrapper:
    def __init__(self):
        self.disabled = os.getenv('MISAKANET_VOICE', '1') == '0'
        self.voice_engine = self._detect_engine()

    def _detect_engine(self) -> Optional[str]:
        """Auto-detect available voice engine"""
        if sys.platform == 'darwin':
            return 'say'
        elif sys.platform == 'win32':
            return 'powershell -Command "Add-Type -AssemblyName System.speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\"$input\")"'
        elif sys.platform == 'linux':
            return 'espeak'
        return None

    def process(self, text: str):
        """Process text through voice engine"""
        if self.disabled or not self.voice_engine:
            return

        try:
            subprocess.run(
                self.voice_engine.replace('$input', text),
                shell=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"[Voice] Engine error: {e}", file=sys.stderr)

def main():
    wrapper = VoiceWrapper()
    for line in sys.stdin:
        wrapper.process(line.strip())

if __name__ == "__main__":
    main()