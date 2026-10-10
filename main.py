import os

def run_verification():
    command = "curl -s misakanet.org/api/fragment/liveness"
    expected_result = "fragment is alive"
    
    print(f"Running command: {command}")
    result = os.popen(command).read().strip()
    
    if result == expected_result:
        print(f"Verification passed: {result}")
    else:
        print(f"Verification failed: Expected {expected_result}, got {result}")

if __name__ == "__main__":
    run_verification()