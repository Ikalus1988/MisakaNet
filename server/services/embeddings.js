const { pipeline } = require('@xenova/transformers');

let _tokenizer = null;
let _model = null;

async function loadModel() {
  if (_model) return;
  _tokenizer = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
  _model = _tokenizer;
}

async function getEmbedding(text) {
  await loadModel();
  const output = await _model(text, { pooling: 'mean', normalize: true });
  return Array.from(output.data);
}

function cosineSimilarity(a, b) {
  if (!a || !b || a.length !== b.length) return 0;
  let dot = 0, normA = 0, normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dot / (Math.sqrt(normA) * Math.sqrt(normB));
}

module.exports = { getEmbedding, cosineSimilarity };
