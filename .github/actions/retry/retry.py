
import sys
import time
import random

def exponential_backoff(max_attempts, backoff_rate):
    for attempt in range(1, int(max_attempts) + 1):
        try:
            # Simulate a task that might fail
            # In a real scenario, this would be the actual command/script execution
            print(f'Attempt {attempt}/{max_attempts}')
            # Simulate failure on first few attempts
            if attempt < int(max_attempts):
                raise Exception("Simulated failure")
            else:
                print("Task succeeded!")
                sys.exit(0)
        except Exception as e:
            print(f'Attempt {attempt} failed: {e}')
            if attempt == int(max_attempts):
                print("Max attempts reached. Exiting.")
                sys.exit(1)
            
            # Calculate backoff time with jitter
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
