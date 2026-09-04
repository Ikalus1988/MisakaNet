const { describe, it, before, after, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const { spawn } = require('node:child_process');
const path = require('node:path');
const fs = require('node:fs');

// Mock MCP Client for testing
class MockMCPClient {
    constructor() {
        this.tools = new Map();
        this.resources = new Map();
        this.connected = false;
    }

    async connect() {
        this.connected = true;
        return true;
    }

    async disconnect() {
        this.connected = false;
        return true;
    }

    async listTools() {
        if (!this.connected) throw new Error('Not connected');
        return Array.from(this.tools.keys());
    }

    async callTool(name, args) {
        if (!this.connected) throw new Error('Not connected');
        const tool = this.tools.get(name);
        if (!tool) throw new Error(`Tool ${name} not found`);
        return tool.handler(args);
    }

    async listResources() {
        if (!this.connected) throw new Error('Not connected');
        return Array.from(this.resources.keys());
    }

    async readResource(uri) {
        if (!this.connected) throw new Error('Not connected');
        const resource = this.resources.get(uri);
        if (!resource) throw new Error(`Resource ${uri} not found`);
        return resource.content;
    }

    // Helper to register mock tools/resources for testing
    registerTool(name, handler) {
        this.tools.set(name, { name, handler });
    }

    registerResource(uri, content) {
        this.resources.set(uri, { uri, content });
    }
}

describe('DSH Plugin Functionality Tests', () => {
    let client;

    before(async () => {
        client = new MockMCPClient();
        await client.connect();
    });

    after(async () => {
        if (client) {
            await client.disconnect();
        }
    });

    describe('Tool Discovery', () => {
        it('should discover misakanet_search tool', async () => {
            // Simulate tool registration as would happen in real plugin
            client.registerTool('misakanet_search', async (args) => {
                return { results: [] };
            });

            const tools = await client.listTools();
            assert.ok(tools.includes('misakanet_search'), 'misakanet_search tool should be available');
        });

        it('should discover misakanet_get_lesson tool', async () => {
            client.registerTool('misakanet_get_lesson', async (args) => {
                return { lesson: null };
            });

            const tools = await client.listTools();
            assert.ok(tools.includes('misakanet_get_lesson'), 'misakanet_get_lesson tool should be available');
        });

        it('should not discover non-existent tools', async () => {
            const tools = await client.listTools();
            assert.ok(!tools.includes('non_existent_tool'), 'Non-existent tool should not be listed');
        });
    });

    describe('Tool Functionality', () => {
        it('should execute misakanet_search with valid arguments', async () => {
            client.registerTool('misakanet_search', async (args) => {
                assert.ok(args.query, 'Query argument is required');
                return { results: [{ title: 'Test Result' }] };
            });

            const result = await client.callTool('misakanet_search', { query: 'test' });
            assert.ok(result.results, 'Search should return results');
            assert.strictEqual(result.results.length, 1);
        });

        it('should execute misakanet_get_lesson with valid arguments', async () => {
            client.registerTool('misakanet_get_lesson', async (args) => {
                assert.ok(args.lessonId, 'Lesson ID argument is required');
                return { lesson: { id: args.lessonId, content: 'Lesson Content' } };
            });

            const result = await client.callTool('misakanet_get_lesson', { lessonId: '123' });
            assert.ok(result.lesson, 'Get lesson should return lesson data');
            assert.strictEqual(result.lesson.id, '123');
        });

        it('should handle tool execution errors gracefully', async () => {
            client.registerTool('misakanet_search', async (args) => {
                throw new Error('Search failed');
            });

            await assert.rejects(
                () => client.callTool('misakanet_search', { query: 'test' }),
                { message: 'Search failed' }
            );
        });
    });

    describe('Resource Access', () => {
        it('should access misaka://lessons/index resource', async () => {
            client.registerResource('misaka://lessons/index', {
                content: JSON.stringify({ lessons: [] })
            });

            const resources = await client.listResources();
            assert.ok(resources.includes('misaka://lessons/index'), 'Lessons index resource should be available');

            const content = await client.readResource('misaka://lessons/index');
            const parsed = JSON.parse(content);
            assert.ok(parsed.lessons, 'Resource should contain lessons array');
        });

        it('should handle non-existent resource access', async () => {
            await assert.rejects(
                () => client.readResource('misaka://nonexistent/resource'),
                { message: 'Resource misaka://nonexistent/resource not found' }
            );
        });

        it('should list all available resources', async () => {
            client.registerResource('misaka://lessons/1', { content: 'Lesson 1' });
            client.registerResource('misaka://lessons/2', { content: 'Lesson 2' });

            const resources = await client.listResources();
            assert.ok(resources.includes('misaka://lessons/1'));
            assert.ok(resources.includes('misaka://lessons/2'));
        });
    });

    describe('Connection State', () => {
        it('should prevent operations when not connected', async () => {
            const disconnectedClient = new MockMCPClient();
            
            await assert.rejects(
                () => disconnectedClient.listTools(),
                { message: 'Not connected' }
            );

            await assert.rejects(
                () => disconnectedClient.callTool('any_tool', {}),
                { message: 'Not connected' }
            );

            await assert.rejects(
                () => disconnectedClient.listResources(),
                { message: 'Not connected' }
            );

            await assert.rejects(
                () => disconnectedClient.readResource('any://resource'),
                { message: 'Not connected' }
            );
        });

        it('should allow operations after reconnection', async () => {
            const testClient = new MockMCPClient();
            await testClient.connect();
            
            testClient.registerTool('test_tool', async () => ({ success: true }));
            
            const tools = await testClient.listTools();
            assert.ok(tools.includes('test_tool'));
            
            await testClient.disconnect();
            
            await assert.rejects(
                () => testClient.listTools(),
                { message: 'Not connected' }
            );
            
            await testClient.connect();
            
            const toolsAfterReconnect = await testClient.listTools();
            assert.ok(toolsAfterReconnect.includes('test_tool'));
            
            await testClient.disconnect();
        });
    });

    describe('Edge Cases', () => {
        it('should handle empty search results', async () => {
            client.registerTool('misakanet_search', async (args) => {
                return { results: [] };
            });

            const result = await client.callTool('misakanet_search', { query: 'nonexistent' });
            assert.strictEqual(result.results.length, 0);
        });

        it('should handle null lesson ID', async () => {
            client.registerTool('misakanet_get_lesson', async (args) => {
                if (!args.lessonId) {
                    throw new Error('Lesson ID is required');
                }
                return { lesson: null };
            });

            await assert.rejects(
                () => client.callTool('misakanet_get_lesson', { lessonId: null }),
                { message: 'Lesson ID is required' }
            );
        });

        it('should handle large resource content', async () => {
            const largeContent = 'x'.repeat(100000);
            client.registerResource('misaka://large/resource', { content: largeContent });

            const content = await client.readResource('misaka://large/resource');
            assert.strictEqual(content.length, 100000);
        });
    });
});