// Regression test for packages/fatal-guard/index.js runHandler function
const assert = require('assert');
const { runHandler } = require('../index.js');

// Mock handler that logs the received payload to a file
function mockHandler(payload, logPath) {
  return async () => {
    await new Promise(resolve => setTimeout(resolve, 100)); // Simulate some processing time
    fs.writeFileSync(logPath, JSON.stringify(payload));
  };
}

// Test that runHandler delivers the payload correctly
test('runHandler delivers payload to handler', async () => {
  const tmpDir = await mkdtemp(path.join(os.tmpdir(), 'fatal-guard-regression-'));
  const logPath = path.join(tmpDir, 'log.txt');
  const payload = { schemaVersion: 1, reason: 'test', timestamp: new Date().toISOString() };

  // Create a mock handler that logs the received payload to a file
  const handler = mockHandler(payload, logPath);

  // Call runHandler with the mock handler and payload
  await runHandler(handler, payload);

  // Read the log file and assert that it contains the correct payload
  const logContent = fs.readFileSync(logPath, 'utf8');
  assert.strictEqual(logContent, JSON.stringify(payload));
});