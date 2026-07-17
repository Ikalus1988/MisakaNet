/**
 * MisakaNet Search API Worker
 * 
 * REST API endpoints for lesson search via HTTP.
 * Enables MCP servers, editors, and other tools to integrate with MisakaNet.
 * 
 * Endpoints:
 *   GET /api/search?q=keyword&domain=devops&limit=10
 *   GET /api/health
 */
import protocol from '../../../misaka-protocol.json';

// Rate limit: 60 requests per minute for unauthenticated users
const RATE_LIMIT = 60;
const RATE_WINDOW_MS = 60 * 1000;

const CACHE_MAX_AGE = 300; // 5 minutes cache for search results

// In-memory rate limit store (per IP)
// For production, use KV with expiration
const rateLimitStore = new Map();

/**
 * Rate limiting middleware
 * Returns true if request is allowed, false if rate limited
 */
function checkRateLimit(clientIP) {
  const now = Date.now();
  const key = `rate:${clientIP}`;
  
  let record = rateLimitStore.get(key);
  if (!record || now - record.windowStart > RATE_WINDOW_MS) {
    // New window
    rateLimitStore.set(key, { count: 1, windowStart: now });
    return true;
  }
  
  if (record.count >= RATE_LIMIT) {
    return false;
  }
  
  record.count++;
  return true;
}

/**
 * Parse query parameters from URL
 */
function parseSearchParams(url) {
  const params = new URL(url).searchParams;
  return {
    q: params.get('q') || '',
    domain: params.get('domain') || null,
    tags: params.get('tags') ? params.get('tags').split(',') : [],
    status: params.get('status') || null,
    offset: parseInt(params.get('offset')) || 0,
    limit: Math.min(parseInt(params.get('limit')) || 10, 100), // Max 100
  };
}

/**
 * Build CORS headers
 */
function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };
}

/**
 * JSON response helper
 */
function jsonResponse(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': `public, max-age=${CACHE_MAX_AGE}`,
      ...corsHeaders(),
      ...extraHeaders,
    },
  });
}

/**
 * Error response helper
 */
function errorResponse(message, status = 400, details = null) {
  const body = { error: message };
  if (details) body.details = details;
  return jsonResponse(body, status);
}

/**
 * Health check endpoint
 * GET /api/health
 */
function handleHealth(env) {
  const health = {
    status: 'ok',
    service: 'misakanet-search-api',
    version: protocol.version || '1.0.0',
    timestamp: new Date().toISOString(),
    features: {
      search: true,
      rateLimit: true,
      rateLimitRequests: RATE_LIMIT,
      rateLimitWindowSeconds: RATE_WINDOW_MS / 1000,
    },
  };
  
  return jsonResponse(health);
}

/**
 * Search endpoint
 * GET /api/search?q=...&domain=...&limit=...&offset=...
 * 
 * Note: This is a proxy to the CLI search functionality.
 * In production, this would call misakanet-core directly or use KV cache.
 * For now, returns a guide to use the CLI.
 */
async function handleSearch(params, clientIP) {
  const { q, domain, tags, status, offset, limit } = params;
  
  // Validate query
  if (!q || q.trim().length === 0) {
    return errorResponse('Query parameter "q" is required', 400);
  }
  
  if (q.length > 500) {
    return errorResponse('Query too long (max 500 characters)', 400);
  }
  
  // Rate limit check
  if (!checkRateLimit(clientIP)) {
    return errorResponse(
      'Rate limit exceeded. Try again in a minute.',
      429,
      {
        limit: RATE_LIMIT,
        windowSeconds: RATE_WINDOW_MS / 1000,
        retryAfter: '60',
      }
    );
  }
  
  // Build response with search metadata
  // Note: In a full implementation, this would call the actual search engine
  // For this implementation, we return the search parameters that would be used
  const searchConfig = {
    query: q.trim(),
    filters: {
      domain: domain,
      tags: tags.length > 0 ? tags : null,
      status: status,
    },
    pagination: {
      offset,
      limit,
      hasMore: true, // Would be calculated based on total results
    },
    meta: {
      rateLimitRemaining: RATE_LIMIT - 1,
      documentation: 'Use the CLI: python3 search_knowledge.py --json "your query"',
      apiVersion: 'v1',
    },
  };
  
  // In production, this would call the actual search engine
  // Example of what the response would look like:
  const mockResults = [
    {
      title: `Result for: ${q}`,
      domain: domain || 'general',
      tags: tags.length > 0 ? tags : ['search'],
      status: status || 'published',
      score: 1.0,
      path: `lessons/example-${Date.now()}.md`,
      preview: `This is a preview of search results for "${q}". In production, this would contain actual matching lessons.`,
    },
  ];
  
  const response = {
    query: q.trim(),
    filters: searchConfig.filters,
    pagination: searchConfig.pagination,
    results: mockResults,
    total: mockResults.length,
    rateLimitRemaining: RATE_LIMIT - 1,
  };
  
  return jsonResponse(response, 200, {
    'X-RateLimit-Limit': String(RATE_LIMIT),
    'X-RateLimit-Remaining': String(RATE_LIMIT - 1),
    'X-RateLimit-Reset': String(Math.floor(Date.now() / RATE_WINDOW_MS) + 1),
  });
}

/**
 * Main request handler
 */
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const clientIP = request.headers.get('CF-Connecting-IP') || 
                     request.headers.get('X-Forwarded-For')?.split(',')[0].trim() ||
                     'unknown';
    
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, {
        status: 204,
        headers: corsHeaders(),
      });
    }
    
    // Route matching
    const path = url.pathname;
    
    if (path === '/api/health' && request.method === 'GET') {
      return handleHealth(env);
    }
    
    if (path === '/api/search' && request.method === 'GET') {
      return handleSearch(parseSearchParams(url), clientIP);
    }
    
    // 404 for unknown paths
    if (path.startsWith('/api/')) {
      return errorResponse(`Unknown endpoint: ${path}`, 404, {
        availableEndpoints: [
          'GET /api/health - Health check',
          'GET /api/search?q=query - Search lessons',
        ],
      });
    }
    
    // Root path
    if (path === '/' || path === '') {
      return jsonResponse({
        service: 'misakanet-search-api',
        version: protocol.version || '1.0.0',
        documentation: 'https://github.com/Ikalus1988/MisakaNet',
        endpoints: {
          health: 'GET /api/health',
          search: 'GET /api/search?q=query&domain=domain&limit=10&offset=0',
        },
      });
    }
    
    return errorResponse('Not found', 404);
  },
};
