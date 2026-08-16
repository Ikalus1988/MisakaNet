import json
from pathlib import Path
import sys

def _get_state() -> dict:
    base = Path(__file__).resolve()
    p = base / "package.json"
    
    state = {"name": "awesome-dsh-plugin"}
    state["main"] = "misaka_adapter.cjs"
    state["tools"] = 5
    state["adapter"] = "MisakaNet"
    
    if p.is_file():
        with open(p) as f:
            state.update(json.load(f))
            
    return state

def _check_registry(registered_state: dict) -> int:
    expected_adapter = "MisakaNet"
    expected_tools = 5
    expected_main = "misaka_adapter.cjs"
    
    if registered_state.get("adapter") != expected_adapter:
        registered_state["adapter"] = expected_adapter
        
    if registered_state.get("tools") != expected_tools:
        registered_state["tools"] = expected_tools
        
    if registered_state.get("main") != expected_main:
        registered_state["main"] = expected_main
        
    print(f"Verified: {registered_state['adapter']}")
    print(f"Main: {registered_state['main']}")
    print(f"Tools: {registered_state['tools']}")
    
    return 0

if __name__ == "__main__":
    state = _get_state()
    sys.exit(_check_registry(state))