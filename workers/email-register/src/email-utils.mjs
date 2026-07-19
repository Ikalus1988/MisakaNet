const MAX_BODY_LENGTH = 20000;

function decodeTransferEncoding(value, encoding = '') {
  const normalized = value.replace(/\r\n/g, '\n');
  if (encoding.toLowerCase() === 'base64') {
    try {
      const binary = atob(normalized.replace(/\s/g, ''));
      return new TextDecoder().decode(Uint8Array.from(binary, char => char.charCodeAt(0)));
    } catch {
      return normalized;
    }
  }
  if (encoding.toLowerCase() === 'quoted-printable') {
    const unfolded = normalized.replace(/=\n/g, '');
    const bytes = [];
    for (let index = 0; index < unfolded.length; index += 1) {
      if (unfolded[index] === '=' && /^[0-9a-f]{2}$/i.test(unfolded.slice(index + 1, index + 3))) {
        bytes.push(parseInt(unfolded.slice(index + 1, index + 3), 16));
        index += 2;
      } else {
        bytes.push(...new TextEncoder().encode(unfolded[index]));
      }
    }
    return new TextDecoder().decode(new Uint8Array(bytes));
  }
  return normalized;
}

function parseHeaders(headerBlock) {
  const headers = new Map();
  const unfolded = headerBlock.replace(/\r?\n[ \t]+/g, ' ');
  for (const line of unfolded.split(/\r?\n/)) {
    const separator = line.indexOf(':');
    if (separator > 0) {
      headers.set(line.slice(0, separator).toLowerCase(), line.slice(separator + 1).trim());
    }
  }
  return headers;
}

function parseMimePart(rawPart) {
  const separator = rawPart.search(/\r?\n\r?\n/);
  const headerBlock = separator >= 0 ? rawPart.slice(0, separator) : '';
  const body = separator >= 0 ? rawPart.slice(separator).replace(/^\r?\n\r?\n/, '') : rawPart;
  const headers = parseHeaders(headerBlock);
  const contentType = headers.get('content-type') || 'text/plain';
  const boundary = contentType.match(/boundary=(?:"([^"]+)"|([^;\s]+))/i)?.slice(1).find(Boolean);

  if (boundary) {
    const parts = body
      .split(`--${boundary}`)
      .slice(1)
      .map(part => part.replace(/^\r?\n/, '').replace(/\r?\n--\s*$/, '').trim())
      .filter(Boolean)
      .map(parseMimePart);
    return parts.find(part => part.type.startsWith('text/plain')) ||
      parts.find(part => part.type.startsWith('text/html')) ||
      { type: 'text/plain', body: '' };
  }

  return {
    type: contentType.toLowerCase(),
    body: decodeTransferEncoding(body, headers.get('content-transfer-encoding')),
  };
}

function decodeHtmlEntitiesOnce(value) {
  const namedEntities = new Map([
    ['amp', '&'],
    ['lt', '<'],
    ['gt', '>'],
    ['quot', '"'],
    ['apos', "'"],
    ['#39', "'"],
    ['nbsp', ' '],
  ]);

  let output = '';
  for (let index = 0; index < value.length; index += 1) {
    if (value[index] !== '&') {
      output += value[index];
      continue;
    }

    const semicolon = value.indexOf(';', index + 1);
    if (semicolon < 0 || semicolon - index > 12) {
      output += value[index];
      continue;
    }

    const entity = value.slice(index + 1, semicolon);
    const lowerEntity = entity.toLowerCase();
    if (namedEntities.has(lowerEntity)) {
      output += namedEntities.get(lowerEntity);
      index = semicolon;
      continue;
    }

    if (lowerEntity.startsWith('#x')) {
      const codePoint = Number.parseInt(lowerEntity.slice(2), 16);
      if (Number.isFinite(codePoint) && codePoint >= 0 && codePoint <= 0x10ffff) {
        output += String.fromCodePoint(codePoint);
        index = semicolon;
        continue;
      }
    } else if (lowerEntity.startsWith('#')) {
      const codePoint = Number.parseInt(lowerEntity.slice(1), 10);
      if (Number.isFinite(codePoint) && codePoint >= 0 && codePoint <= 0x10ffff) {
        output += String.fromCodePoint(codePoint);
        index = semicolon;
        continue;
      }
    }

    output += value.slice(index, semicolon + 1);
    index = semicolon;
  }
  return output;
}

function readTagName(value, tagStart) {
  let index = tagStart + 1;
  if (value[index] === '/') index += 1;
  while (value[index] === ' ' || value[index] === '\t' || value[index] === '\n') index += 1;

  const nameStart = index;
  while (index < value.length && /[A-Za-z0-9:-]/.test(value[index])) index += 1;
  return value.slice(nameStart, index).toLowerCase();
}

function htmlToText(value) {
  let output = '';
  let index = 0;
  let suppressedTag = '';
  const newlineTags = new Set(['br', 'div', 'li', 'p', 'tr']);

  while (index < value.length) {
    const char = value[index];
    if (char !== '<') {
      if (!suppressedTag) output += char;
      index += 1;
      continue;
    }

    const tagEnd = value.indexOf('>', index + 1);
    if (tagEnd < 0) {
      if (!suppressedTag) output += char;
      index += 1;
      continue;
    }

    const tagName = readTagName(value, index);
    const isClosingTag = value[index + 1] === '/';

    if (suppressedTag) {
      if (isClosingTag && tagName === suppressedTag) suppressedTag = '';
      index = tagEnd + 1;
      continue;
    }

    if (!isClosingTag && (tagName === 'script' || tagName === 'style')) {
      suppressedTag = tagName;
      index = tagEnd + 1;
      continue;
    }

    if (tagName && (newlineTags.has(tagName) || (isClosingTag && newlineTags.has(tagName)))) {
      output += '\n';
    }
    index = tagEnd + 1;
  }

  return collapseRepeatedBlankLines(decodeHtmlEntitiesOnce(output));
}

function collapseRepeatedBlankLines(value) {
  const result = [];
  for (const line of value.replace(/\r\n/g, '\n').split('\n')) {
    const trimmedRight = line.trimEnd();
    if (trimmedRight.trim() === '') continue;
    result.push(trimmedRight);
  }
  return result.join('\n');
}

/** Extract the human-readable text part from a raw RFC 5322 message. */
export function parseEmailBody(rawEmail) {
  const part = parseMimePart(rawEmail);
  let body = part.body;
  if (part.type.startsWith('text/html')) {
    body = htmlToText(body);
  }
  return body.replace(/\0/g, '').trim().slice(0, MAX_BODY_LENGTH);
}

/** Remove common reply quoting so the stored lesson is the new submission. */
export function extractLessonContent(body) {
  const lines = body.replace(/\r\n/g, '\n').split('\n');
  const replyStart = lines.findIndex(line => /^On .+wrote:\s*$/i.test(line) || /^-{2,}\s*Original Message\s*-{2,}$/i.test(line));
  const freshLines = (replyStart >= 0 ? lines.slice(0, replyStart) : lines)
    .filter(line => !line.trimStart().startsWith('>'));
  return freshLines.join('\n').trim().slice(0, MAX_BODY_LENGTH);
}

export function detectIntakeType(subject, body) {
  const searchable = `${subject}\n${body.slice(0, 2000)}`.toLowerCase();
  if (/\b(register|registration|join)\b|注册/.test(searchable)) return 'registration';
  if (/\b(lesson|learning|postmortem)\b|投稿|教训|課程/.test(searchable)) return 'lesson-submission';
  if (/\b(bug|issue|defect)\b/.test(searchable)) return 'bug-report';
  return 'unknown';
}

export function buildReplyText({ intakeId, intakeType, nodeId }) {
  const identifier = nodeId ? `Your node ID is ${nodeId}.` : `Your intake ID is ${intakeId}.`;
  return [
    'Thanks for contacting MisakaNet.',
    '',
    identifier,
    `Submission type: ${intakeType}`,
    '',
    nodeId
      ? 'Next steps: clone https://github.com/Ikalus1988/MisakaNet and follow the node quickstart.'
      : 'Your submission is queued for maintainer review. Keep the intake ID for follow-up.',
  ].join('\n');
}
