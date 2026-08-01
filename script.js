const danmakuToggle = document.getElementById('danmaku-toggle');
const danmakuInput = document.getElementById('danmaku-input');
const danmakuText = document.getElementById('danmaku-text');
const danmakuSend = document.getElementById('danmaku-send');
const danmakuDisplay = document.getElementById('danmaku-display');

let isDanmakuOn = true;

// Toggle danmaku
danmakuToggle.addEventListener('click', () => {
    isDanmakuOn = !isDanmakuOn;
    danmakuToggle.textContent = isDanmakuOn ? '💬 Danmaku ON' : '💬 Danmaku OFF';
    localStorage.setItem('isDanmakuOn', isDanmakuOn);
    if (isDanmakuOn) {
        danmakuInput.style.display = 'block';
    } else {
        danmakuInput.style.display = 'none';
    }
});

// Send danmaku
danmakuSend.addEventListener('click', () => {
    const text = danmakuText.value.trim();
    if (text) {
        // Post danmaku to API
        fetch('/api/danmaku', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text })
        })
        .then(response => response.json())
        .then(data => {
            // Display danmaku
            const danmakuElement = document.createElement('div');
            danmakuElement.textContent = text;
            danmakuDisplay.appendChild(danmakuElement);
            // Scroll to bottom
            danmakuDisplay.scrollTop = danmakuDisplay.scrollHeight;
        })
        .catch(error => console.error(error));
        danmakuText.value = '';
    }
});

// Poll last 50 danmaku
setInterval(() => {
    fetch('/api/danmaku')
    .then(response => response.json())
    .then(data => {
        // Display danmaku
        danmakuDisplay.innerHTML = '';
        data.forEach(danmaku => {
            const danmakuElement = document.createElement('div');
            danmakuElement.textContent = danmaku.text;
            danmakuDisplay.appendChild(danmakuElement);
        });
    })
    .catch(error => console.error(error));
}, 10000);