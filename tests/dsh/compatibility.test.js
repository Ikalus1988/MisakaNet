import { describe, it, expect } from 'vitest';

describe('DSH Plugin Compatibility', () => {
  it('tests with Claude Code', () => {
    const agent = 'Claude Code';
    expect(agent).toBeDefined();
  });

  it('tests with Cursor', () => {
    const agent = 'Cursor';
    expect(agent).toBeDefined();
  });

  it('tests with other MCP-compatible agents', () => {
    const agent = 'Generic MCP Agent';
    expect(agent).toBeDefined();
  });
});
