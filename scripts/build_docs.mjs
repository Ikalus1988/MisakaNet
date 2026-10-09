#!/usr/bin/env node
/**
 * Build script to convert markdown docs to HTML
 * Processes docs/ directory and creates index.html files
 */

import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = join(fileURLToPath(import.meta.url), '..');
const ROOT = join(__dirname, '..');
const DOCS_DIR = join(ROOT, 'docs');

function markdownToHtml(markdown) {
  return markdown
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2">$1</a>')
    .replace(/\n/g, '<br/>');
}

function createHtmlPage(title, content) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${title} - MisakaNet</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
    h1 { color: #333; }
    code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
  </style>
</head>
<body>
  ${content}
</body>
</html>`;
}

async function buildDocFile(filePath) {
  const content = await readFile(filePath, 'utf-8');
  const htmlContent = markdownToHtml(content);
  return createHtmlPage('Documentation', htmlContent);
}

async function processDirectory(dirPath) {
  const entries = await readdir(dirPath, { withFileTypes: true });
  
  for (const entry of entries) {
    const fullPath = join(dirPath, entry.name);
    
    if (entry.isDirectory()) {
      await processDirectory(fullPath);
    } else if (entry.name.endsWith('.md')) {
      const htmlPath = fullPath.replace('.md', '.html');
      const htmlContent = await buildDocFile(fullPath);
      await writeFile(htmlPath, htmlContent, 'utf-8');
      console.log(`Built: ${htmlPath.replace(ROOT + '/', '')}`);
    }
  }
}

async function main() {
  console.log('Building documentation site...');
  
  try {
    await processDirectory(DOCS_DIR);
    console.log('Documentation build complete!');
  } catch (error) {
    console.error('Build failed:', error.message);
    process.exit(1);
  }
}

main();
