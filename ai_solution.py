For #3658:

When replacing an entire text file, the patch should be the entire content of the file as a single line. Use `applyPatch` with the entire content as the patch.

```typescript
const newContent = fileContent;
const patch = {
  type: "applyPatch",
  content: {
    changes: [{text: newContent, version: 1}]
  }
};
```

For #3663:

The macOS window can't have height or width exceeding 512, and position can't go beyond 2048. The origin is fixed, so position adjustments are centered.

```typescript
const window = {
  height: Math.min(512, desiredHeight),
  width: Math.min(512, desiredWidth),
  x: Math.min(2048, desiredX),
  y: Math.min(2048, desiredY)
};
```