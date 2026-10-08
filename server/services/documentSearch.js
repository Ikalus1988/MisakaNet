const { cosineSimilarity } = require('./embeddings');
const { listPublishedDocuments } = require('./documents');

/**
 * Search documents by embedding similarity.
 * Returns results sorted descending by score.
 */
async function searchDocuments(queryEmbedding, top = 3) {
  const documents = await listPublishedDocuments();

  const scored = documents.map(doc => ({
    id: doc.id,
    title: doc.title,
    score: cosineSimilarity(queryEmbedding, doc.embedding),
  }));

  scored.sort((a, b) => b.score - a.score);

  return scored.slice(0, top);
}

module.exports = { searchDocuments };
