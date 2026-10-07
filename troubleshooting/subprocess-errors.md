# subprocess.CalledProcessError Troubleshooting

## Context
Issue #1553 - Command execution failures in Go applications

## Error Analysis
```go
// Common error scenario
cmd := exec.Command("some-command", "arg1", "arg2")
output, err := cmd.CombinedOutput()
if err != nil {
    if exitErr, ok := err.(*exec.ExitError); ok {
        // Handle specific exit code
        status := exitErr.ExitCode()
        fmt.Printf("Command failed with status %d\n", status)
    }
}
```

## Debugging Steps
1. Capture full command output
2. Check environment variables
3. Verify command availability
4. Test with different working directories

## Verification
```go
func testCommand() error {
    cmd := exec.Command("echo", "test")
    cmd.Dir = "/tmp"
    
    output, err := cmd.CombinedOutput()
    if err != nil {
        return fmt.Errorf("command failed: %v, output: %s", err, output)
    }
    return nil
}
```

## Common Solutions
- Add proper error wrapping
- Implement retry logic
- Add timeout mechanisms
