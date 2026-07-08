\# Bug Report: Invalid Authorization Header Format in Moorcheh API



\## Summary

The Moorcheh API returns a 403 error when using the provided API key, with the message: "Invalid key=value pair (missing equal-sign) in Authorization header". This occurs because the API key format does not include the required `=` character in the hash.



\## Steps to Reproduce

1\. Set up Memanto with a valid Moorcheh API key.

2\. Run the test script `memanto\_bug\_test\_v2.py`.

3\. Observe the 403 error responses.



\### Test Script

```python

import requests



API\_KEY = "YOUR\_API\_KEY"

url = "https://api.moorcheh.ai/v1/memory"

headers = {"Authorization": f"Bearer {API\_KEY}"}

response = requests.get(url, headers=headers)

print(response.status\_code, response.text)

