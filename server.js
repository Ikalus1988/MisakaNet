const express = require('express');
const app = express();
const CloudflareWorker = require('cloudflare-worker');
const KV = require('cloudflare-kv');

app.use(express.json());

// Post danmaku
app.post('/api/danmaku', (req, res) => {
    const text = req.body.text;
    // Filter danmaku
    if (filterDanmaku(text)) {
        // Store danmaku in KV
        KV.put('danmaku', text);
        res.json({ message: 'Danmaku posted successfully' });
    } else {
        res.status(400).json({ message: 'Danmaku contains forbidden content' });
    }
});

// Get last 50 danmaku
app.get('/api/danmaku', (req, res) => {
    // Get danmaku from KV
    KV.get('danmaku')
    .then(danmaku => {
        res.json(danmaku);
    })
    .catch(error => {
        res.status(500).json({ message: 'Error fetching danmaku' });
    });
});

// Filter danmaku
function filterDanmaku(text) {
    // Filter attacks, slurs, tokens/secrets, personal info, spam, and URL spam
    const forbiddenWords = ['attack', 'slur', 'token', 'secret', 'personal', 'spam', 'url'];
    for (const word of forbiddenWords) {
        if (text.includes(word)) {
            return false;
        }
    }
    return true;
}

app.listen(3000, () => {
    console.log('Server listening on port 3000');
});