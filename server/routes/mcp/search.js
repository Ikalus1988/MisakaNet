const { getEmbedding } = require('../../services/embeddings');
const { searchDocuments } = require('../../services/documentSearch');
const { getDocumentById } = require('../../services/documents');

// Default relevance floor: scores below this are treated as no-match.
// Chosen to cleanly separate irrelevant hits (~3) from relevant ones (~11+).
const RELEVANCE_FLOOR = 5;

async function searchHandler(req, res) {
  const { query, top = 3, detail } = req.body?.params?.arguments || {};

  if (!query) {
    res.status(400).json({ jsonrpc: '2.0', id: req.body?.id, error: { code: -32602, message: 'query is required' } });
    return;
  }

  let embedding;
  try {
    embedding = await getEmbedding(query);
  } catch (err) {
    res.status(500).json({ jsonrpc: '2.0', id: req.body?.id, error: { code: -32000, message: err.message } });
    return;
  }

  let results;
  try {
    results = await searchDocuments(embedding, top);
  } catch (err) {
    res.status(500).json({ jsonrpc: '2.0', id: req.body?.id, error: { code: -32000, message: err.message } });
    return;
  }

  // Filter out results below the relevance floor when full detail is NOT requested.
  // When detail=full, return all results so the caller can inspect scores themselves.
  const passedFloor = results.filter(r => r.score >= RELEVANCE_FLOOR);

  if (passedFloor.length === 0 && detail !== 'full') {
    // No relevant results — return no_match shape (consistent with existing obscure-query behavior)
    res.json({
      jsonrpc: '2.0',
      id: req.body?.id,
      result: {
        content: [{ type: 'text', text: 'lesson-found' }],
        voice: 'lesson-found',
        no_match: null,
        hits: [],
      },
    });
    return;
  }

  const hits = (detail === 'full' ? results : passedFloor).map(r => ({
    id: r.id,
    title: r.title,
    score: detail === 'full' ? r.score : undefined,
  }));

  res.json({
    jsonrpc: '2.0',
    id: req.body?.id,
    result: {
      content: [{ type: 'text', text: hits.length > 0 ? 'lesson-found' : 'lesson-found' }],
      voice: hits.length > 0 ? 'lesson-found' : 'no_match',
      no_match: hits.length === 0 ? 'none' : null,
      hits,
    },
  });
}

module.exports = { searchHandler };
