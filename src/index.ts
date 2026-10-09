import { Hono } from 'hono'
import { serveStatic } from 'hono/cloudflare-workers'

const app = new Hono()

// Serve static files from /docs (includes built HTML files)
app.use('/docs/*', serveStatic({ 
  root: './docs',
  rewriteRequestPath: (path) => path.replace(/^\/docs/, '')
}))

// Root route
app.get('/', (c) => c.html(`
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MisakaNet</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
    h1 { color: #333; }
    nav a { margin-right: 16px; }
  </style>
</head>
<body>
  <h1>Welcome to MisakaNet</h1>
  <nav>
    <a href="/docs/">Documentation</a>
  </nav>
  <p>Visit <a href="/docs/">/docs/</a> for the full documentation.</p>
</body>
</html>
`))

export default app
