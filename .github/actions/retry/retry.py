
import subprocess
import sys
import time
import random

def exponential_backoff(max_attempts, backoff_rate):
    for attempt in range(1, int(max_attempts) + 1):
        try:
            print(f'Attempt {attempt}/{max_attempts}')
            result = subprocess.run(
                ['pytest', '--cov=scripts', '--cov=misakanet', '--cov-report=term', '--cov-fail-under=20', 'tests/'],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f'Attempt {attempt} failed with exit code {result.returncode}')
                if attempt < int(max_attempts):
                    backoff_time = (backoff_rate ** attempt) * (1 + random.uniform(-0.2, 0.2))
                    print(f'Waiting for {backoff_time:.2f} seconds before next retry...')
                    time.sleep(backoff_time)
                    continue
                else:
                    print('Max attempts reached. Tests failed.')
                    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                    sys.exit(1)
            else:
                print('All tests passed!')
                print(result.stdout[-1000:] if len(result.stdout) > 1000 else result.stdout)
                sys.exit(0)
        except Exception as e:
            print(f'Attempt {attempt} failed: {e}')
            if attempt == int(max_attempts):
                print('Max attempts reached. Exiting.')
                sys.exit(1)
            backoff_time = (backoff_rate ** attempt) * (1 + random.uniform(-0.2, 0.2))
            print(f'Waiting for {backoff_time:.2f} seconds before next retry...')
            time.sleep(backoff_time)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python retry.py <max_attempts> <backoff_rate>")
        sys.exit(1)
    
    max_attempts = int(sys.argv[1])
    backoff_rate = int(sys.argv[2])
    
    exponential_backoff(max_attempts, backoff_rate)
