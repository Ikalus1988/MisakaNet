// integrations/mcp/server.js — MCP Streamable HTTP endpoint for MisakaNet (closes #804)
const http = require('http');
const { execSync } = require('child_process');
const path = require('path');

const MISAKANET_ROOT = path.resolve(__dirname, '../..');
const PORT = process.env.MCP_PORT || 3456;

// MCP Tool definitions
const tools = [
  {
    name: 'misaka_search',
    description: 'Search MisakaNet knowledge base for lessons, references, and solutions',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query' },
        type: { type: 'string', enum: ['all', 'lessons', 'ref', 'titles'], description: 'Search type filter' },
        limit: { type: 'number', description: 'Max results (default 10)' }
      },
      required: ['query']
    }
  },
  {
    name: 'misaka_contribute',
    description: 'Contribute a new lesson to MisakaNet knowledge base',
    inputSchema: {
      type: 'object',
      properties: {
        title: { type: 'string', description: 'Lesson title' },
        domain: { type: 'string', description: 'Knowledge domain' },
        tags: { type: 'string', description: 'Comma-separated tags' },
        content: { type: 'string', description: 'Lesson content in markdown' }
      },
      required: ['title', 'content']
    }
  },
  {
    name: 'misaka_crash_tombstone',
    description: 'Submit a crash tombstone — captures failure data for the swarm to learn from',
    inputSchema: {
      type: 'object',
      properties: {
        command: { type: 'string', description: 'Command that crashed' },
        error: { type: 'string', description: 'Error message' },
        stack: { type: 'string', description: 'Stack trace' },
        node: { type: 'string', description: 'Node identifier (optional)' }
      },
      required: ['error']
    }
  },
  {
    name: 'misaka_failure_map',
    description: 'Query the privacy-preserving unsolved failure map',
    inputSchema: {
      type: 'object',
      properties: {
        domain: { type: 'string', description: 'Filter by domain' },
        count: { type: 'number', description: 'Max results (default 20)' }
      }
    }
  }
];

// In-memory failure map store
const failureMap = [];
const MAX_FAILURES = 1000;

function searchMisakaNet(query, type = 'all', limit = 10) {
  try {
    const output = execSync(
      `python3 ${MISAKANET_ROOT}/search_knowledge.py "${query}"${type !== 'all' ? ' --' + type : ''}`,
      { encoding: 'utf-8', timeout: 10000, maxBuffer: 1024 * 1024 }
    );
    return { success: true, results: output.trim().split('\n').slice(0, limit) };
  } catch (e) {
    return { success: false, error: e.message, fallback: `If python3 is not available, manually search in ${MISAKANET_ROOT}/data/` };
  }
}

function contributeLesson(title, domain, tags, content) {
  try {
    const tagStr = tags ? `--tags "${tags}"` : '';
    execSync(
      `python3 ${MISAKANET_ROOT}/scripts/queue_lesson.py -t "${title}" -d ${domain || 'general'} ${tagStr} "${content.replace(/"/g, '\\"')}"`,
      { encoding: 'utf-8', timeout: 10000 }
    );
    return { success: true, message: `Lesson "${title}" queued for contribution` };
  } catch (e) {
    return { success: false, error: e.message, fallback: 'Save lesson manually as markdown in data/lessons/' };
  }
}

function submitTombstone(command, error, stack, node) {
  const tombstone = {
    id: `tomb_${Date.now()}_${Math.random().toString(36).slice(2,6)}`,
    command: command || 'unknown',
    error,
    stack: stack || '',
    node: node || 'anon',
    timestamp: new Date().toISOString(),
    resolved: false
  };
  failureMap.push(tombstone);
  if (failureMap.length > MAX_FAILURES) failureMap.shift();
  return { success: true, tombstone: { id: tombstone.id, message: 'Tombstone recorded — the swarm learns from this' } };
}

function getFailureMap(domain, count = 20) {
  let results = failureMap.filter(f => !f.resolved);
  if (domain) results = results.filter(f => f.error.toLowerCase().includes(domain.toLowerCase()));
  results = results.slice(-count).reverse();
  return {
    count: results.length,
    total: failureMap.filter(f => !f.resolved).length,
    failures: results.map(f => ({
      id: f.id,
      command: f.command.slice(0, 50),
      error: f.error.slice(0, 120),
      node: f.node,
      timestamp: f.timestamp
    }))
  };
}

// MCP HTTP server
const server = http.createServer((req, res) => {
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Access-Control-Allow-Origin', '*');
  
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.writeHead(204);
    res.end();
    return;
  }

  // MCP endpoint
  if (req.method === 'POST' && req.url === '/mcp') {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      try {
        const msg = JSON.parse(body);
        
        // MCP Initialize
        if (msg.method === 'initialize') {
          res.end(JSON.stringify({
            jsonrpc: '2.0',
            id: msg.id,
            result: {
              protocolVersion: '0.2.0',
              serverInfo: { name: 'misaka-net-mcp', version: '1.0.0' },
              capabilities: { tools: {} }
            }
          }));
          return;
        }

        // List tools
        if (msg.method === 'tools/list') {
          res.end(JSON.stringify({
            jsonrpc: '2.0',
            id: msg.id,
            result: { tools }
          }));
          return;
        }

        // Call tool
        if (msg.method === 'tools/call') {
          const { name, arguments: args } = msg.params;
          let result;
          switch (name) {
            case 'misaka_search':
              result = searchMisakaNet(args.query, args.type, args.limit);
              break;
            case 'misaka_contribute':
              result = contributeLesson(args.title, args.domain, args.tags, args.content);
              break;
            case 'misaka_crash_tombstone':
              result = submitTombstone(args.command, args.error, args.stack, args.node);
              break;
            case 'misaka_failure_map':
              result = getFailureMap(args.domain, args.count);
              break;
            default:
              res.end(JSON.stringify({ jsonrpc: '2.0', id: msg.id, error: { code: -32601, message: `Unknown tool: ${name}` } }));
              return;
          }
          res.end(JSON.stringify({ jsonrpc: '2.0', id: msg.id, result: { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] } }));
          return;
        }

        res.end(JSON.stringify({ jsonrpc: '2.0', id: msg.id, error: { code: -32601, message: `Unknown method: ${msg.method}` } }));
      } catch (e) {
        res.end(JSON.stringify({ jsonrpc: '2.0', error: { code: -32700, message: e.message } }));
      }
    });
    return;
  }

  // Health check
  if (req.url === '/health') {
    res.end(JSON.stringify({ status: 'ok', uptime: process.uptime(), failures: failureMap.length }));
    return;
  }

  // 404
  res.writeHead(404);
  res.end(JSON.stringify({ error: 'Not found', endpoints: ['POST /mcp', 'GET /health'] }));
});

server.listen(PORT, () => {
  console.log(`🔌 MisakaNet MCP server running on http://localhost:${PORT}`);
  console.log(`   POST /mcp — MCP endpoint`);
  console.log(`   GET /health — Health check`);
});

module.exports = { server, searchMisakaNet, contributeLesson, submitTombstone, getFailureMap };
