# JSON-LD Schema for MisakaNet

## Overview
Add structured data to help AI agents understand your site.

## HTML Template

Add this to your main HTML template (e.g., `templates/base.html` or `layout.html`):

```html
<!-- JSON-LD Structured Data for AI Agents -->
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "name": "MisakaNet",
      "url": "https://misakanet.org",
      "description": "Git-backed failure-memory for AI coding agents. Zero dependencies. Zero server. Zero database.",
      "potentialAction": {
        "@type": "SearchAction",
        "target": {
          "@type": "EntryPoint",
          "urlTemplate": "https://misakanet.org/api/search?q={search_term_string}",
          "actionPlatform": [
            "http://schema.org/DesktopWebPlatform",
            "http://schema.org/MobileWebPlatform"
          ]
        },
        "query-input": "required name=search_term_string"
      }
    },
    {
      "@type": "Dataset",
      "name": "Failure Lessons Knowledge Base",
      "description": "Structured dataset of failure-recovery lessons for AI coding agents",
      "url": "https://misakanet.org/lessons",
      "distribution": {
        "@type": "DataDownload",
        "contentUrl": "https://misakanet.org/api/summary",
        "encodingFormat": "application/json"
      },
      "license": "https://misakanet.org/license",
      "creator": {
        "@type": "Organization",
        "name": "MisakaNet Contributors",
        "url": "https://github.com/Ikalus1988/MisakaNet"
      }
    },
    {
      "@type": "SoftwareApplication",
      "name": "MisakaNet MCP Server",
      "applicationCategory": "DeveloperApplication",
      "operatingSystem": "Cross-platform",
      "description": "MCP server providing failure-recovery lessons to AI coding agents",
      "url": "https://github.com/Ikalus1988/MisakaNet",
      "downloadUrl": "https://pypi.org/project/misakanet/",
      "softwareVersion": "2.21.0",
      "offers": {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "USD"
      }
    }
  ]
}
</script>

<!-- Open Graph Meta Tags -->
<meta property="og:title" content="MisakaNet - Failure-Memory for AI Agents" />
<meta property="og:description" content="Git-backed failure-memory for AI coding agents. 310+ lessons." />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://misakanet.org" />
<meta property="og:image" content="https://misakanet.org/promotional/misaka-compare.jpg" />

<!-- Twitter Card Meta Tags -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="MisakaNet - Failure-Memory for AI Agents" />
<meta name="twitter:description" content="Git-backed failure-memory for AI coding agents. 310+ lessons." />
<meta name="twitter:image" content="https://misakanet.org/promotional/misaka-compare.jpg" />

<!-- AI Agent Support Headers -->
<meta name="ai-agent-support" content="true" />
<meta name="content-signals-policy" content="allow" />
<meta name="misaka-status" content="verified" />
```

## Validation

Test your structured data:
1. Google Rich Results Test: https://search.google.com/test/rich-results
2. Schema.org Validator: https://validator.schema.org/

## Benefits

- **Search Engines**: Better understanding of site structure
- **AI Agents**: Clear data access points
- **Rich Results**: Enhanced search snippets
- **Knowledge Graph**: Potential inclusion in knowledge panels

## Deployment

1. Add the HTML template to your main layout
2. Deploy to production
3. Test with Google Rich Results Test
4. Monitor in Google Search Console
