#!/usr/bin/env node
/**
 * sign-plugin-package.mjs — 给 .cindy 插件包加「发布者签名」（Cindy 插件信任链 v1）
 *
 * 口径严格对齐客户端（Cindy Electron app.asar 里的 verifyGhostZipSignatures /
 * buildStatement / normalizeDocument / canonicalJson），所以本脚本签出来的包能被宿主
 * 认成「有签名」；口径差一个字节，宿主会直接拒装（file-invalid: 签名验证失败）。
 *
 *   签名文件：包内插件目录下 cindy-signatures.json
 *   statement: { schemaVersion:1, ghostId, ghostVersion, files:[{path,sha256,bytes}] }
 *     · files 只含插件目录下的文件（跳过目录条目、__MACOSX、签名文件自身）
 *     · path 相对插件目录；sha256 = 文件内容 SHA256 hex；bytes = 解压后字节数
 *     · 数组按 path.localeCompare 排序
 *   publisher: { algorithm:'ed25519', keyId, name, publicKey(base64 SPKI DER), signature }
 *     · keyId = 'ed25519:' + sha256(SPKI DER).hex.slice(0,32)
 *   签名载荷 = canonicalJson({ statement, publisher:{algorithm,keyId,name,publicKey} })
 *     · canonicalJson = 对象键按字典序递归排序后的 JSON.stringify
 *
 * 私钥纪律：私钥只在本机文件里，脚本任何输出都不含私钥内容；不要把私钥放进仓库、
 * .cindy 包或聊天记录。keyId 与公钥可以公开（公钥是公开印章样本）。
 *
 * 用法：
 *   node scripts/sign-plugin-package.mjs keygen  --key <私钥路径>
 *   node scripts/sign-plugin-package.mjs sign    --package <pkg.cindy> --key <私钥路径> \
 *                                                 --name <发布者名> [--emit-to <插件源码目录>]
 *   node scripts/sign-plugin-package.mjs release --package <pkg.cindy> --key <私钥路径> \
 *                                                 --name <发布者名> --emit-to <插件源码目录>
 *   node scripts/sign-plugin-package.mjs verify  --package <pkg.cindy> [--trust <ghost-trust.json>]
 *
 * --key - 表示从标准输入读私钥 PEM（例如 op read "op://Personal/MisakaNet Plugin Key" | ... sign --key -）。
 */

import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';

const SIGNATURE_FILE = 'cindy-signatures.json';

/* ── canonical JSON（与客户端 canonicalJson$3 逐字一致）──────────────────────── */
function canonicalJson(value) {
  return JSON.stringify(value, (_key, val) => {
    if (val && typeof val === 'object' && !Array.isArray(val)) {
      const out = {};
      for (const key of Object.keys(val).sort()) out[key] = val[key];
      return out;
    }
    return val;
  });
}

function sha256Hex(buf) {
  return crypto.createHash('sha256').update(buf).digest('hex');
}

/* ── 最小 zip 读取器（只读中央目录 + 本地头，够算清单用）────────────────────── */
function readZipEntries(buf) {
  let eocd = -1;
  const floor = Math.max(0, buf.length - 22 - 0xffff);
  for (let i = buf.length - 22; i >= floor; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('不是有效的 zip：找不到 EOCD');

  const count = buf.readUInt16LE(eocd + 10);
  let off = buf.readUInt32LE(eocd + 16);
  const entries = [];

  for (let i = 0; i < count; i++) {
    if (buf.readUInt32LE(off) !== 0x02014b50) throw new Error('zip 中央目录损坏');
    const method = buf.readUInt16LE(off + 10);
    const compSize = buf.readUInt32LE(off + 20);
    const nameLen = buf.readUInt16LE(off + 28);
    const extraLen = buf.readUInt16LE(off + 30);
    const commentLen = buf.readUInt16LE(off + 32);
    const localOff = buf.readUInt32LE(off + 42);
    const name = buf.toString('utf8', off + 46, off + 46 + nameLen);

    const isDir = name.endsWith('/');
    let content = Buffer.alloc(0);
    if (!isDir) {
      const lNameLen = buf.readUInt16LE(localOff + 26);
      const lExtraLen = buf.readUInt16LE(localOff + 28);
      const start = localOff + 30 + lNameLen + lExtraLen;
      const raw = buf.subarray(start, start + compSize);
      if (method === 0) content = Buffer.from(raw);
      else if (method === 8) content = zlib.inflateRawSync(raw);
      else throw new Error(`不支持的压缩方式 ${method}（${name}）`);
    }

    entries.push({ name, isDir, content });
    off += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

/** 包内插件目录前缀；逐字对齐客户端 detectSingleTopFolderPrefix。 */
function pluginPrefix(entries) {
  let top = null;
  for (const e of entries) {
    const name = e.name.replace(/\\/g, '/');
    const slash = name.indexOf('/');
    if (slash <= 0) return '';               // 有根级文件 → 平铺
    const segment = name.slice(0, slash);
    if (top === null) top = segment;
    else if (top !== segment) return '';     // 多个顶层目录 → 当作平铺
  }
  return top === null ? '' : `${top}/`;
}

/* ── statement：与客户端 buildStatement 完全同口径 ──────────────────────────── */
function buildStatement(entries, prefix, manifest) {
  const files = [];
  const ordered = [...entries].sort((a, b) => a.name.localeCompare(b.name));
  for (const e of ordered) {
    if (e.isDir) continue;
    if (e.name.startsWith('__MACOSX/')) continue;
    if (!e.name.startsWith(prefix)) continue;
    const rel = e.name.slice(prefix.length);
    if (!rel || rel === SIGNATURE_FILE) continue;
    files.push({ path: rel, sha256: sha256Hex(e.content), bytes: e.content.length });
  }
  files.sort((a, b) => a.path.localeCompare(b.path));
  return {
    schemaVersion: 1,
    ghostId: manifest.id,
    ghostVersion: manifest.version,
    files,
  };
}

/* ── 密钥 ──────────────────────────────────────────────────────────────────── */
function publicKeyId(spkiDer) {
  return `ed25519:${sha256Hex(spkiDer).slice(0, 32)}`;
}

function loadKey(keyPath) {
  const pem = keyPath === '-' ? fs.readFileSync(0, 'utf8') : fs.readFileSync(keyPath, 'utf8');
  const privateKey = crypto.createPrivateKey(pem);
  const spkiDer = crypto.createPublicKey(privateKey).export({ type: 'spki', format: 'der' });
  return { privateKey, spkiDer, publicKeyB64: spkiDer.toString('base64'), keyId: publicKeyId(spkiDer) };
}

function generateKey(keyPath) {
  if (fs.existsSync(keyPath)) throw new Error(`私钥已存在，不覆盖：${keyPath}`);
  const { privateKey } = crypto.generateKeyPairSync('ed25519');
  const pem = privateKey.export({ type: 'pkcs8', format: 'pem' });
  fs.mkdirSync(path.dirname(keyPath), { recursive: true });
  fs.writeFileSync(keyPath, pem, { mode: 0o600 });
  try { fs.chmodSync(keyPath, 0o600); } catch { /* Windows 上可能不支持 */ }
  const spkiDer = crypto.createPublicKey(privateKey).export({ type: 'spki', format: 'der' });
  return { privateKey, spkiDer, publicKeyB64: spkiDer.toString('base64'), keyId: publicKeyId(spkiDer) };
}

/* ── 签名文档 ──────────────────────────────────────────────────────────────── */
function signDocument(statement, key, publisherName) {
  const publisherCore = {
    algorithm: 'ed25519',
    keyId: key.keyId,
    name: publisherName,
    publicKey: key.publicKeyB64,
  };
  const payload = Buffer.from(canonicalJson({ statement, publisher: publisherCore }), 'utf8');
  const signature = crypto.sign(null, payload, key.privateKey).toString('base64');
  return { schemaVersion: 1, statement, publisher: { ...publisherCore, signature } };
}

/** 客户端 normalizeDocument 的最小复核：字段类型/长度/格式。 */
function validateDocument(doc) {
  const fail = (why) => { throw new Error(`签名文档不合法：${why}`); };
  if (!doc || typeof doc !== 'object') fail('不是对象');
  if (doc.schemaVersion !== 1) fail('schemaVersion 必须为 1');
  const st = doc.statement;
  if (!st || st.schemaVersion !== 1) fail('statement.schemaVersion 必须为 1');
  if (typeof st.ghostId !== 'string' || typeof st.ghostVersion !== 'string') fail('ghostId/ghostVersion 必须是字符串');
  if (!Array.isArray(st.files)) fail('files 必须是数组');
  for (const f of st.files) {
    if (!f || typeof f !== 'object') fail('files 里有非对象项');
    if (typeof f.path !== 'string') fail('files[].path 必须是字符串');
    if (!/^[a-f0-9]{64}$/.test(String(f.sha256))) fail('files[].sha256 必须是 64 位小写 hex');
    if (!Number.isSafeInteger(f.bytes) || f.bytes < 0) fail('files[].bytes 必须是非负安全整数');
  }
  const pub = doc.publisher;
  if (!pub || pub.algorithm !== 'ed25519') fail('publisher.algorithm 必须是 ed25519');
  if (typeof pub.keyId !== 'string' || typeof pub.name !== 'string') fail('publisher.keyId/name 必须是字符串');
  if (!pub.name.trim().length || pub.name.length > 64) fail('publisher.name 长度必须在 1..64');
  if (typeof pub.publicKey !== 'string' || typeof pub.signature !== 'string') fail('publisher.publicKey/signature 必须是字符串');
  return true;
}

/* ── CLI ───────────────────────────────────────────────────────────────────── */
function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const key = a.slice(2);
      const next = argv[i + 1];
      if (next === undefined || next.startsWith('--')) out[key] = true;
      else { out[key] = next; i++; }
    } else out._.push(a);
  }
  return out;
}

function readManifestFromPackage(entries, prefix) {
  const entry = entries.find((e) => e.name === `${prefix}ghost.json`);
  if (!entry) throw new Error('包里找不到 ghost.json');
  return JSON.parse(entry.content.toString('utf8'));
}

function cmdKeygen(args) {
  const keyPath = args.key;
  if (!keyPath || keyPath === true) throw new Error('用法：keygen --key <私钥路径>');
  const key = generateKey(path.resolve(keyPath));
  console.log(JSON.stringify({
    ok: true,
    keyPath: path.resolve(keyPath),
    keyId: key.keyId,
    publicKey: key.publicKeyB64,
    note: '私钥已写入本机文件（脚本不打印其内容）。请离线备份，且不要提交进任何仓库。',
  }, null, 2));
}

function cmdSign(args) {
  const pkgPath = args.package;
  const keyPath = args.key;
  const name = args.name;
  if (!pkgPath || pkgPath === true) throw new Error('用法：sign --package <pkg.cindy> --key <私钥> --name <发布者名>');
  if (!keyPath || keyPath === true) throw new Error('缺少 --key');
  if (!name || name === true) throw new Error('缺少 --name');

  const buf = fs.readFileSync(pkgPath);
  const entries = readZipEntries(buf);
  const prefix = pluginPrefix(entries);
  const manifest = readManifestFromPackage(entries, prefix);
  const statement = buildStatement(entries, prefix, manifest);
  const key = loadKey(keyPath === '-' ? '-' : path.resolve(keyPath));
  const doc = signDocument(statement, key, name);
  validateDocument(doc);

  const outPath = args.out && args.out !== true ? path.resolve(args.out) : null;
  const json = JSON.stringify(doc, null, 2);
  if (outPath) fs.writeFileSync(outPath, json + '\n');
  if (args['emit-to'] && args['emit-to'] !== true) {
    const dir = path.resolve(args['emit-to']);
    fs.writeFileSync(path.join(dir, SIGNATURE_FILE), json + '\n');
  }

  console.log(JSON.stringify({
    ok: true,
    package: path.resolve(pkgPath),
    prefix,
    ghostId: manifest.id,
    ghostVersion: manifest.version,
    files: statement.files.length,
    statementSha256: sha256Hex(Buffer.from(canonicalJson(statement), 'utf8')),
    publisherName: name,
    keyId: key.keyId,
    publicKey: key.publicKeyB64,
    signatureDocument: outPath ?? null,
    emittedInto: args['emit-to'] && args['emit-to'] !== true ? path.resolve(args['emit-to'], SIGNATURE_FILE) : null,
    note: '签好后重新打包（pack 会带上 cindy-signatures.json），再安装验证：宿主会按同一口径复算清单，装得上就说明口径一致。',
  }, null, 2));
}

function cmdRelease(args) {
  // 一步到位：密钥不存在就当场生成（私钥只落本机文件、脚本不打印），然后对包签名并写回源码目录。
  // 正式密钥建议由发布者本人执行本命令 —— 私钥不该经过对话/Agent。
  const keyPath = args.key;
  const pkgPath = args.package;
  const name = args.name;
  if (!keyPath || keyPath === true) throw new Error('用法：release --package <pkg.cindy> --key <私钥路径> --name <发布者名>');
  if (!pkgPath || pkgPath === true) throw new Error('缺少 --package');
  if (!name || name === true) throw new Error('缺少 --name');

  let created = false;
  if (keyPath !== '-' && !fs.existsSync(path.resolve(keyPath))) {
    generateKey(path.resolve(keyPath));
    created = true;
  }
  const key = loadKey(keyPath === '-' ? '-' : path.resolve(keyPath));

  const buf = fs.readFileSync(pkgPath);
  const entries = readZipEntries(buf);
  const prefix = pluginPrefix(entries);
  const manifest = readManifestFromPackage(entries, prefix);
  const statement = buildStatement(entries, prefix, manifest);
  const doc = signDocument(statement, key, name);
  validateDocument(doc);
  const json = JSON.stringify(doc, null, 2);

  const emitTo = args['emit-to'] && args['emit-to'] !== true ? path.resolve(args['emit-to']) : null;
  if (emitTo) fs.writeFileSync(path.join(emitTo, SIGNATURE_FILE), json + '\n');
  const outPath = args.out && args.out !== true ? path.resolve(args.out) : null;
  if (outPath) fs.writeFileSync(outPath, json + '\n');

  console.log(JSON.stringify({
    ok: true,
    keyCreated: created,
    keyPath: keyPath === '-' ? '(stdin)' : path.resolve(keyPath),
    keyId: key.keyId,
    publicKey: key.publicKeyB64,
    package: path.resolve(pkgPath),
    ghostId: manifest.id,
    ghostVersion: manifest.version,
    files: statement.files.length,
    statementSha256: sha256Hex(Buffer.from(canonicalJson(statement), 'utf8')),
    publisherName: name,
    emittedInto: emitTo ? path.join(emitTo, SIGNATURE_FILE) : null,
    note: '重新打包（pack 会带上 cindy-signatures.json）后安装，宿主会按同一口径复算清单并验签；装得上就说明口径一致。',
  }, null, 2));
}

function cmdVerify(args) {
  const pkgPath = args.package;
  if (!pkgPath || pkgPath === true) throw new Error('用法：verify --package <pkg.cindy>');
  const buf = fs.readFileSync(pkgPath);
  const entries = readZipEntries(buf);
  const prefix = pluginPrefix(entries);
  const manifest = readManifestFromPackage(entries, prefix);
  const sigEntry = entries.find((e) => e.name === `${prefix}${SIGNATURE_FILE}`);
  if (!sigEntry) {
    console.log(JSON.stringify({ ok: true, signed: false, level: 'unverified', label: '未验 / 无签名' }, null, 2));
    return;
  }
  const doc = JSON.parse(sigEntry.content.toString('utf8'));
  validateDocument(doc);
  const expected = buildStatement(entries, prefix, manifest);
  const statementMatches = canonicalJson(doc.statement) === canonicalJson(expected);

  const spkiDer = Buffer.from(doc.publisher.publicKey, 'base64');
  const keyIdOk = publicKeyId(spkiDer) === doc.publisher.keyId;
  const payload = Buffer.from(canonicalJson({
    statement: doc.statement,
    publisher: {
      algorithm: doc.publisher.algorithm,
      keyId: doc.publisher.keyId,
      name: doc.publisher.name,
      publicKey: doc.publisher.publicKey,
    },
  }), 'utf8');
  const signatureOk = crypto.verify(
    null,
    payload,
    crypto.createPublicKey({ key: spkiDer, format: 'der', type: 'spki' }),
    Buffer.from(doc.publisher.signature, 'base64'),
  );

  let level = 'unverified';
  let label = '未验 / 无签名';
  if (statementMatches && keyIdOk && signatureOk) {
    level = 'signed-unverified';
    label = '有签名，然发布者身分未验';
    const trustPath = args.trust && args.trust !== true ? path.resolve(args.trust) : null;
    if (trustPath && fs.existsSync(trustPath)) {
      const trust = JSON.parse(fs.readFileSync(trustPath, 'utf8'));
      const entry = trust?.publishers?.[doc.publisher.keyId];
      if (entry && entry.publicKey === doc.publisher.publicKey) {
        level = 'verified-publisher';
        label = '发布者已验';
      }
    }
  }

  console.log(JSON.stringify({
    ok: statementMatches && keyIdOk && signatureOk,
    signed: true,
    statementMatches,
    keyIdOk,
    signatureOk,
    level,
    label,
    publisherName: doc.publisher.name,
    keyId: doc.publisher.keyId,
    files: doc.statement.files.length,
    ghostVersion: doc.statement.ghostVersion,
  }, null, 2));
  if (!(statementMatches && keyIdOk && signatureOk)) process.exitCode = 1;
}

const args = parseArgs(process.argv.slice(2));
const cmd = args._[0];
try {
  if (cmd === 'keygen') cmdKeygen(args);
  else if (cmd === 'sign') cmdSign(args);
  else if (cmd === 'release') cmdRelease(args);
  else if (cmd === 'verify') cmdVerify(args);
  else {
    console.error('用法：sign-plugin-package.mjs <keygen|sign|verify> [选项]');
    process.exitCode = 2;
  }
} catch (err) {
  console.error(`失败：${err instanceof Error ? err.message : String(err)}`);
  process.exitCode = 1;
}
