import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '../..');
const FIXTURES_DIR = path.join(__dirname, 'fixtures');

describe('MisakaNet DSH Plugin - Agent Compatibility Tests', () => {
  const agentConfigsPath = path.join(FIXTURES_DIR, 'agent-configs.json');
  const agentConfigs = JSON.parse(fs.readFileSync(agentConfigsPath, 'utf8'));

  describe('3.1 Claude Code Compatibility', () => {
    it('should validate Claude Code MCP and SKILL.md configuration', () => {
      const claudeConfig = agentConfigs.claude_code;
      assert.ok(claudeConfig.mcpServers.misakanet, 'Claude Code must define misakanet MCP server');
      assert.equal(claudeConfig.mcpServers.misakanet.command, 'python3');

      const skillPath = path.join(REPO_ROOT, claudeConfig.skills[0]);
      assert.ok(fs.existsSync(skillPath), `Skill file must exist at ${skillPath}`);

      const skillContent = fs.readFileSync(skillPath, 'utf8');
      assert.ok(skillContent.includes('# MisakaNet') || skillContent.includes('misakanet'), 'Skill content must contain header');
    });

    it('should have well-formed markdown instructions in SKILL.md for Claude agents', () => {
      const skillPath = path.join(REPO_ROOT, 'SKILL.md');
      const content = fs.readFileSync(skillPath, 'utf8');

      assert.ok(content.length > 500, 'SKILL.md should provide comprehensive instructions');
      assert.ok(content.includes('```'), 'SKILL.md should provide actionable code blocks');
    });
  });

  describe('3.2 Cursor IDE Compatibility', () => {
    it('should validate Cursor MCP server configuration structure', () => {
      const cursorConfig = agentConfigs.cursor;
      assert.ok(cursorConfig.mcp.servers['misakanet-local'], 'Cursor config must include misakanet-local');
      assert.equal(cursorConfig.mcp.servers['misakanet-local'].command, 'python3');
      assert.ok(Array.isArray(cursorConfig.mcp.servers['misakanet-local'].args));
      assert.equal(cursorConfig.mcp.servers['misakanet-local'].args[0], 'scripts/mcp_server.py');
    });

    it('should verify environment variables schema for Cursor agents', () => {
      const cursorServer = agentConfigs.cursor.mcp.servers['misakanet-local'];
      assert.ok(cursorServer.env, 'env configuration object must exist');
      assert.ok('MISAKA_DEBUG' in cursorServer.env, 'MISAKA_DEBUG option should be configurable');
    });
  });

  describe('3.3 DeepSeek Harness & Multi-Agent Adapter Compatibility', () => {
    it('should validate DeepSeek recovery adapter tool contract', () => {
      const dshConfig = agentConfigs.dsh_harness;
      assert.ok(dshConfig.mcpServers['misakanet-recovery'], 'DSH harness must declare recovery MCP');
      assert.equal(dshConfig.mcpServers['misakanet-recovery'].args[0], 'scripts/mcp_deepseek_adapter.py');

      const adapterPath = path.join(REPO_ROOT, 'scripts', 'mcp_deepseek_adapter.py');
      assert.ok(fs.existsSync(adapterPath), 'Adapter script must exist in repository');
    });

    it('should verify tool naming mapping contract between MisakaNet and DeepSeek Harness', () => {
      const expectedMappings = {
        'misakanet.search': 'deepseek.recovery.search',
        'misakanet.get_lesson': 'deepseek.recovery.get_lesson',
        'misakanet.submit_usage': 'deepseek.recovery.submit_feedback',
        'misakanet.usage_status': 'deepseek.recovery.status'
      };

      const adapterScript = fs.readFileSync(path.join(REPO_ROOT, 'scripts', 'mcp_deepseek_adapter.py'), 'utf8');
      for (const [misakaTool, dshTool] of Object.entries(expectedMappings)) {
        assert.ok(adapterScript.includes(dshTool), `Adapter must implement ${dshTool}`);
      }
    });
  });
});
