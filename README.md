# MisakaNet

An intelligent multi-agent system for distributed knowledge extraction and collaboration.

## Features

- **Multi-Agent Architecture**: Coordinate multiple AI agents for complex tasks
- **Tool System**: Extensible tool ecosystem with pluggable integrations
- **Knowledge Base**: Distributed knowledge storage and retrieval
- **API Integration**: REST API for external tool access
- **Docker Support**: Easy deployment with Docker

## Installation

```bash
# Clone the repository
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet

# Install dependencies
npm install

# Build the project
npm run build

# Run the application
npm start
```

## Usage

```typescript
import { webFetchTool } from './tools/web-fetch.js';

const result = await webFetchTool.execute({
  url: 'https://example.com',
  timeout: 10000
});

if (result.success) {
  console.log('Content:', result.content);
} else {
  console.error('Error:', result.error);
}
```

## Tools

### web_fetch

Fetch content from a URL and extract text.

**Parameters:**
- `url` (required): The URL to fetch
- `timeout` (optional): Request timeout in milliseconds (default: 10000)
- `retries` (optional): Number of retry attempts (default: 3)

**Example:**
```typescript
await webFetchTool.execute({
  url: 'https://github.com/awesome-dsh-plugin/awesome-dsh-plugin/blob/main/README.zh.md?plain=1'
});
```

## Testing

```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in watch mode
npm run test:watch
```

## License

AGPL-3.0
