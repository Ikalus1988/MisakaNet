import 'reflect-metadata';
import { config } from 'dotenv';
import { Logger } from './utils/logger.js';
import { webFetchTool } from './tools/web-fetch.js';
import type { Tool } from './tools/types.js';

// Load environment variables
config();

const logger = new Logger('MisakaNet');

// Initialize tools
const tools: Tool[] = [
  webFetchTool
];

// Export for testing
export { tools, webFetchTool };

// Main entry point
async function main() {
  logger.info('MisakaNet starting...');
  
  // Log initialized tools
  logger.info(`Initialized ${tools.length} tools:`);
  for (const tool of tools) {
    logger.info(`  - ${tool.name}: ${tool.description}`);
  }
  
  logger.info('MisakaNet is ready');
}

// Run if executed directly
if (require.main === module) {
  main().catch((error) => {
    logger.error('Failed to start MisakaNet:', error);
    process.exit(1);
  });
}
