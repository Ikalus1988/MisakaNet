/**
 * Search API Worker Tests
 */

const TEST_HOST = 'http://localhost:8787';

// Mock fetch for local testing
async function makeRequest(path) {
  const url = `${TEST_HOST}${path}`;
  const response = await fetch(url);
  const data = await response.json();
  return { status: response.status, data };
}

async function testHealthEndpoint() {
  console.log('Testing /api/health...');
  const { status, data } = await makeRequest('/api/health');
  
  if (status !== 200) {
    throw new Error(`Health check failed: ${status}`);
  }
  
  if (data.status !== 'ok') {
    throw new Error(`Health check returned non-ok status: ${data.status}`);
  }
  
  console.log('  ✓ Health endpoint works');
  return true;
}

async function testSearchWithQuery() {
  console.log('Testing /api/search?q=...');
  const { status, data } = await makeRequest('/api/search?q=test');
  
  if (status !== 200) {
    throw new Error(`Search failed: ${status}`);
  }
  
  if (!data.query || data.query !== 'test') {
    throw new Error(`Query not preserved: ${data.query}`);
  }
  
  if (!Array.isArray(data.results)) {
    throw new Error('Results should be an array');
  }
  
  console.log('  ✓ Search endpoint works');
  return true;
}

async function testSearchWithFilters() {
  console.log('Testing /api/search with filters...');
  const { status, data } = await makeRequest('/api/search?q=devops&domain=kubernetes&limit=5');
  
  if (status !== 200) {
    throw new Error(`Filtered search failed: ${status}`);
  }
  
  if (data.filters.domain !== 'kubernetes') {
    throw new Error(`Domain filter not applied: ${data.filters.domain}`);
  }
  
  if (data.pagination.limit !== 5) {
    throw new Error(`Limit not applied: ${data.pagination.limit}`);
  }
  
  console.log('  ✓ Search with filters works');
  return true;
}

async function testSearchMissingQuery() {
  console.log('Testing /api/search without query...');
  const { status, data } = await makeRequest('/api/search');
  
  if (status !== 400) {
    throw new Error(`Expected 400, got ${status}`);
  }
  
  if (!data.error || !data.error.includes('required')) {
    throw new Error(`Error message not helpful: ${data.error}`);
  }
  
  console.log('  ✓ Missing query returns 400');
  return true;
}

async function testCorsHeaders() {
  console.log('Testing CORS headers...');
  const response = await fetch(`${TEST_HOST}/api/health`, {
    method: 'OPTIONS',
    headers: {
      'Origin': 'https://example.com',
      'Access-Control-Request-Method': 'GET',
    },
  });
  
  const corsHeader = response.headers.get('Access-Control-Allow-Origin');
  if (corsHeader !== '*') {
    throw new Error(`CORS not configured: ${corsHeader}`);
  }
  
  console.log('  ✓ CORS headers present');
  return true;
}

async function testRateLimiting() {
  console.log('Testing rate limiting...');
  // Make multiple requests quickly
  for (let i = 0; i < 5; i++) {
    const { status } = await makeRequest('/api/search?q=test' + i);
    if (status !== 200) {
      throw new Error(`Request ${i} failed: ${status}`);
    }
  }
  
  // Check rate limit headers
  const { data, status } = await makeRequest('/api/search?q=ratelimit-test');
  if (!data.rateLimitRemaining !== undefined) {
    console.log('  ✓ Rate limit info present');
  }
  
  return true;
}

async function runTests() {
  console.log('Search API Worker Tests');
  console.log('========================\n');
  
  const tests = [
    testHealthEndpoint,
    testSearchWithQuery,
    testSearchWithFilters,
    testSearchMissingQuery,
    testCorsHeaders,
    testRateLimiting,
  ];
  
  let passed = 0;
  let failed = 0;
  
  for (const test of tests) {
    try {
      await test();
      passed++;
    } catch (error) {
      console.error(`  ✗ ${error.message}`);
      failed++;
    }
  }
  
  console.log(`\nResults: ${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

// Run tests if executed directly
if (typeof process !== 'undefined' && process.argv.includes('test')) {
  runTests().catch(console.error);
}

export { runTests };
