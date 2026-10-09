```ts
export function generationOf(version: string): 'legacy' | 'modern' {
  if (version === undefined) return "legacy";
  const match = /^(\d+)\.(\d+)\./u.exec(version);
  if (match === null) return "legacy";
  const major = Number(match[1]);
  const minor = Number(match[2]);
  return major > 0 || minor >= 87 ? "modern" : "legacy";
}
