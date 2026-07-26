---
{"title": "Creating Engaging Single-File HTML Presentations with Bento Slides", "domain": "web-development", "tags": ["presentation", "html", "animation", "design-systems"], "language": "en", "status": "published", "source": "https://bento.page/slides/", "created": "2026-07-27", "confidence": "0.85"}
---

## Problem

A presenter needs to create an interactive PowerPoint-style presentation but wants to distribute it as a single self-contained HTML file that supports editing, viewing, real-time collaboration, and embedded data without external dependencies or file conversions. Traditional presentation tools require multiple files, server infrastructure, or export steps that break interactivity.

## Root Cause

Presentation tools typically separate the presentation layer (slides), data layer (charts), and editing interface into different files or require server backends. This fragmentation makes single-file distribution impossible and prevents seamless collaboration. HTML5 with canvas/SVG can handle all three concerns in one file, but requires purposeful design patterns for animation, morphing between slides, and stateful elements.

## Solution

Build presentations using Bento's single-file HTML architecture with the following techniques:

1. **Structure slides with semantic elements and stable IDs for morphing**

```html
<div id="hero-1" class="slide">
  <img id="hero-image" src="data:image/..." />
  <h1 id="title-text">Welcome</h1>
</div>
<div id="hero-2" class="slide">
  <img id="hero-image" src="data:image/..." />
  <h1 id="title-text">Key Findings</h1>
</div>
```

Keep the same `id` across consecutive slides so elements morph smoothly instead of popping in/out.

2. **Apply ambient motion effects to static content**

```javascript
const slideConfig = {
  fx: {
    ambient: "kenburns",
    ken: {
      dir: "drift",
      scale: 1.08,
      duration: 20
    }
  }
};
```

Apply Ken-Burns drift effect to hero images and cover slides (slow zoom + pan). Add `transition: "morph"` between related slides.

3. **Convert text numbers to animated count-ups**

```javascript
{
  fx: { countUp: true },
  value: 1019,
  format: "number"
}
```

Use count-up animations for headline statistics instead of static text renders.

4. **Create visual sequences with looping paths**

```javascript
{
  fx: {
    loop: {
      type: "dash-march",
      duration: 8
    }
  }
}
```

Use dashing/marching effects for timelines, flows, or connection diagrams to indicate process continuation.

5. **Embed data visualizations and charts directly**

Render charts as SVG or canvas elements inline rather than as images. This allows data updates without file regeneration.

6. **Include speaker notes in the file structure**

```html
<div class="slide" data-speaker-notes="This slide introduces the three key findings from Q3 research...">
  <!-- slide content -->
</div>
```

Speaker notes travel with the presentation file for offline use.

## Verification

Audit your presentation before finishing using this checklist:

```bash
# Verify all numbers are animated, not static
grep -n "fx.*countUp" slides.html | wc -l
# Expected: At least 3-5 instances for key metrics

# Check for stable IDs across consecutive slides
grep -E "id=\"[^\"]+\"" slides.html | sort | uniq -d
# Expected: hero-image, title-text, logo-id appear multiple times

# Confirm motion effects on cover/divider slides
grep -c "ambient.*kenburns\|loop.*dash-march" slides.html
# Expected: At least 1 per cover/section divider

# Validate speaker notes embedded
grep -c "data-speaker-notes" slides.html
# Expected: >= slide count / 2

# Test single-file integrity
wc -c slides.html | awk '{if ($1 < 50000000) print "✓ File size reasonable"; else print "✗ File too large"}'
```

## Notes

This architecture generalizes to:

- **Documentation sites** that need interactive walkthroughs within a single HTML file
- **Email templates** that require motion (some clients support CSS animations)
- **Embedded dashboards** in static sites where collaboration isn't needed
- **Offline-first tools** like Obsidian or Logseq extensions

Constraints:
- Keep one accent color and at most two typefaces per presentation
- Maintain 96px side margins for text readability
- Avoid drill-down interactions (use separate state slides instead)
- Test morphing transitions between slides sharing element IDs

## References

- **Source:** https://bento.page/slides/
- **HN Discussion:** Show HN: Bento - An entire PowerPoint in one HTML file (1019 points)