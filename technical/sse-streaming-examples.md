# SSE Streaming for nano-gpt.c

## Context
Issue #1555 - Server-Sent Events implementation for nano-gpt.c

## Implementation Pattern
```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// SSE header configuration
void setup_sse_headers(FILE *response) {
    fprintf(response, "Content-Type: text/event-stream\n");
    fprintf(response, "Cache-Control: no-cache\n");
    fprintf(response, "Connection: keep-alive\n");
    fprintf(response, "\n");
}

// Send SSE event
void send_sse_event(FILE *response, const char *event, const char *data) {
    fprintf(response, "event: %s\n", event);
    fprintf(response, "data: %s\n\n", data);
    fflush(response);
}
```

## Usage Examples
```c
// Streaming completion
void stream_completion(const char *prompt) {
    FILE *response = stdout;
    setup_sse_headers(response);
    
    // Simulate token generation
    for (int i = 0; i < 100; i++) {
        char data[256];
        snprintf(data, sizeof(data), "Token %d", i);
        send_sse_event(response, "token", data);
    }
}
```

## Verification
1. Test with curl: `curl -N http://localhost:8080/stream`
2. Monitor event delivery
3. Measure latency and throughput
