const r = require('../src/lib/redact');

const cases = [
  { name: 'jwt',            input: 'Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozw' },
  { name: 'dsn',            input: 'postgres://user:pass@localhost:5432/db' },
  { name: 'aws_key',        input: 'AKIA1234567890123456' },
  { name: 'github_token',   input: 'ghp_' + 'a'.repeat(36) },
  { name: 'openai_key',     input: 'sk-' + 'a'.repeat(32) },
  { name: 'long_token',     input: 'x' .repeat(45) },
  { name: 'authz_header',   input: 'authorization: Bearer somevalue' },
];

let passed = 0;
for (const c of cases) {
  const result = r.redact(c.input);
  const ok = result.includes('REDACTED');
  if (ok) passed++;
  console.log(`${ok ? '✓' : '✗'} ${c.name}: ${result.slice(0, 70)}`);
}
console.log(`\n${passed}/${cases.length} patterns passed`);
process.exit(passed === cases.length ? 0 : 1);
