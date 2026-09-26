To resolve the issue where the PDF remains alive after writing, add `page.close()` after generating the PDF.

```javascript
// Example code snippet with the fix
await page.waitForPDF();
page.close();
```