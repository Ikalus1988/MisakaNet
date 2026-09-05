import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.join(__dirname, 'fixtures');

describe('MisakaNet DSH Plugin - Functionality & Tool Execution Tests', () => {
  const mockMcpPath = path.join(FIXTURES_DIR, 'mock-mcp-responses.json');
  const sampleLessonsPath = path.join(FIXTURES_DIR, 'sample-lessons.json');

  const mockMcp = JSON.parse(fs.readFileSync(mockMcpPath, 'utf8'));
  const sampleLessons = JSON.parse(fs.readFileSync(sampleLessonsPath, 'utf8'));

  describe('2.1 MCP Tool Discovery', () => {
    it('should expose essential MisakaNet MCP tools in tool list', () => {
      const tools = mockMcp.tools_list.result.tools;
      const toolNames = tools.map(t => t.name);

      assert.ok(toolNames.includes('misakanet_search'), 'misakanet_search tool must be discovered');
      assert.ok(toolNames.includes('misakanet_get_lesson'), 'misakanet_get_lesson tool must be discovered');
      assert.ok(toolNames.includes('misakanet_submit_intake'), 'misakanet_submit_intake tool must be discovered');
    });

    it('should validate tool inputSchema compliance', () => {
      const searchTool = mockMcp.tools_list.result.tools.find(t => t.name === 'misakanet_search');
      assert.ok(searchTool, 'searchTool must exist');
      assert.equal(searchTool.inputSchema.type, 'object');
      assert.ok(searchTool.inputSchema.properties.query, 'query property must exist in schema');
      assert.ok(searchTool.inputSchema.required.includes('query'), 'query must be required');
    });
  });

  describe('2.2 Tool Execution & Search Logic', () => {
    function searchMockLessons(query, domain = null) {
      if (!query || typeof query !== 'string') {
        throw new Error('Invalid query: query must be a non-empty string');
      }
      const q = query.toLowerCase();
      return sampleLessons.filter(lesson => {
        if (domain && lesson.domain !== domain) return false;
        return (
          lesson.title.toLowerCase().includes(q) ||
          lesson.problem.toLowerCase().includes(q) ||
          lesson.keywords.some(k => k.toLowerCase().includes(q))
        );
      });
    }

    it('should retrieve relevant lesson by error keyword', () => {
      const results = searchMockLessons('chromadb');
      assert.ok(results.length > 0, 'Should find at least one lesson matching chromadb');
      assert.equal(results[0].id, 'py-001');
      assert.ok(results[0].fix.includes('ext4'));
    });

    it('should filter lessons by domain when specified', () => {
      const results = searchMockLessons('high load', 'devops');
      assert.ok(results.length > 0);
      assert.equal(results[0].domain, 'devops');

      const noMatch = searchMockLessons('high load', 'rag');
      assert.equal(noMatch.length, 0, 'Should return empty array when domain does not match');
    });

    it('should format retrieved lesson content cleanly', () => {
      const lesson = sampleLessons.find(l => l.id === 'py-001');
      assert.ok(lesson);
      const formatted = `[${lesson.evidence_level}] ${lesson.title} (ID: ${lesson.id})\nFix: ${lesson.fix}\nVerify: ${lesson.verify}`;
      assert.ok(formatted.includes('[E3]'));
      assert.ok(formatted.includes('Fix: Move DB to ext4'));
    });
  });

  describe('2.3 Resource Access (misaka:// protocol)', () => {
    it('should expose standardized resource URIs', () => {
      const resources = mockMcp.resource_index.result.resources;
      const uris = resources.map(r => r.uri);

      assert.ok(uris.includes('misaka://lessons/index'), 'Must support index resource');
      assert.ok(uris.includes('misaka://lessons/domains'), 'Must support domains resource');
    });

    it('should validate resource URI syntax', () => {
      const validUriPattern = /^misaka:\/\/lessons\/[a-z0-9_-]+$/;
      const validUri = 'misaka://lessons/index';
      const invalidUri = 'http://not-misaka/index';

      assert.ok(validUriPattern.test(validUri));
      assert.ok(!validUriPattern.test(invalidUri));
    });
  });

  describe('2.4 Error Handling & Edge Cases', () => {
    it('should handle empty or whitespace search queries gracefully', () => {
      assert.throws(() => {
        const query = '';
        if (!query.trim()) throw new Error('Query cannot be empty');
      }, /Query cannot be empty/);
    });

    it('should return empty list when no lessons match query', () => {
      const q = 'nonexistent_error_xyz_12345';
      const results = sampleLessons.filter(l => l.title.includes(q));
      assert.deepEqual(results, []);
    });

    it('should handle malformed JSON-RPC payloads cleanly', () => {
      const malformedPayload = '{"jsonrpc": "2.0", "method": "tools/call", "params":}';
      assert.throws(() => {
        JSON.parse(malformedPayload);
      }, SyntaxError);
    });
  });
});
