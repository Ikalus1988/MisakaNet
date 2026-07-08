import requests
import threading
import time
import json
import sys

API_KEY = "TU_API_KEY"
AGENT_ID = "test_agent_concurrent"
BASE_URL = "https://api.moorcheh.ai/v1"

def write_memory(content):
    url = f"{BASE_URL}/memory"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "agent_id": AGENT_ID,
        "content": content
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print(f"[OK] Escrito: {content[:30]}...")
            return True
        else:
            print(f"[ERR] Codigo {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"[EXC] {e}")
        return False

def test_concurrent_writes():
    memories = [f"Memoria concurrente {i}" for i in range(50)]
    results = []
    
    threads = []
    for content in memories:
        thread = threading.Thread(target=lambda: results.append(write_memory(content)))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    success_count = sum(results)
    print(f"\n[RESULTADO] {success_count}/{len(memories)} memorias escritas correctamente")
    return success_count == len(memories)

def test_memory_read():
    url = f"{BASE_URL}/memory/{AGENT_ID}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Lectura exitosa: {len(data.get('memories', []))} memorias encontradas")
            return True
        else:
            print(f"[ERR] Lectura fallida: {response.status_code}")
            return False
    except Exception as e:
        print(f"[EXC] {e}")
        return False

def test_memory_consistency():
    print("\n[TEST] Probando consistencia de memoria...")
    
    url = f"{BASE_URL}/memory"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "agent_id": AGENT_ID,
        "content": "Memoria de prueba con metadatos",
        "metadata": {"source": "test", "timestamp": time.time()}
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            print("[OK] Memoria con metadatos escrita correctamente")
            
            read_response = requests.get(f"{BASE_URL}/memory/{AGENT_ID}", headers=headers)
            if read_response.status_code == 200:
                data = read_response.json()
                memories = data.get('memories', [])
                found = any('metadata' in m for m in memories)
                if found:
                    print("[OK] Metadatos conservados correctamente")
                    return True
                else:
                    print("[ERR] Metadatos no encontrados en la lectura")
                    return False
        else:
            print(f"[ERR] Error al escribir memoria con metadatos: {response.status_code}")
            return False
    except Exception as e:
        print(f"[EXC] {e}")
        return False

def main():
    print("[INFO] Ejecutando pruebas de Memanto...")
    
    tests = [
        ("Concurrencia", test_concurrent_writes),
        ("Lectura", test_memory_read),
        ("Consistencia", test_memory_consistency)
    ]
    
    results = {}
    for name, func in tests:
        print(f"\n[TEST] {name}...")
        results[name] = func()
    
    print("\n" + "="*50)
    print("📊 RESULTADOS FINALES")
    print("="*50)
    for name, result in results.items():
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        print(f"  {name}: {status}")
    
    if any(not r for r in results.values()):
        print("\n🐛 ¡BUG ENCONTRADO!")
        print("📝 Documenta el error y abre un PR en: https://github.com/moorcheh-ai/memanto")
    else:
        print("\n✅ No se encontraron bugs en estas pruebas.")
        print("🔍 Prueba con más carga o casos límite.")

if __name__ == "__main__":
    main()
