---
{
  "title": "एजेंट त्रुटि हैंडलिंग — पुनर्प्रयास और फॉलबैक पैटर्न",
  "domain": "agents",
  "tags": [
    "agent",
    "error-handling",
    "hindi",
    "resilience",
    "tutorial"
  ],
  "source": "manual",
  "status": "published",
  "confidence": 0.85,
  "created": "2026-08-01",
  "lang": "hi",
  "author": "Liona Can",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

## समस्या

AI एजेंट बाहरी सेवाओं (API, MCP सर्वर, डेटाबेस) को कॉल करते समय विफल हो सकते हैं। बिना उचित त्रुटि हैंडलिंग के, एक विफलता पूरे कार्य को रोक सकती है।

## मूल कारण

एजेंट आमतौर पर "खुश पथ" (happy path) के लिए लिखे जाते हैं। त्रुटि मार्ग (error paths) को अनदेखा किया जाता है, जिससे:
- अनंत लूप (infinite loops)
- डेटा हानि (data loss)
- संसाधन रिसाव (resource leaks)

## समाधान

**तीन-स्तरीय त्रुटि हैंडलिंग:**

```python
import asyncio
from typing import Optional

async def resilient_call(func, *args, max_retries=3, fallback=None):
    """पुनर्प्रयास और फॉलबैक के साथ लचीला कॉल।"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await func(*args)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                # एक्सपोनेंशियल बैकऑफ
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
    
    # सभी प्रयास विफल - फॉलबैक का उपयोग करें
    if fallback:
        return await fallback(*args)
    
    raise last_error
```

## सत्यापन

1. पुनर्प्रयास तर्क का परीक्षण करें
2. फॉलबैक व्यवहार का सत्यापन करें
3. बैकऑफ समय की जांच करें

## नोट्स

- हमेशा अधिकतम पुनर्प्रयास सेट करें
- एक्सपोनेंशियल बैकऑफ का उपयोग करें
- फॉलबैक हमेशा प्रदान करें
- त्रुटियों को लॉग करें

## स्रोत

चीनी पाठ से अनुवाद, लेखक zsxh1990।
