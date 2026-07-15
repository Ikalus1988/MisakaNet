/**
 * MisakaNet Registration Worker
 * 
 * 三通道注册 + 防滥用机制
 * 
 * 防御层:
 *   1. Turnstile CAPTCHA（Web 表单）
 *   2. KV Rate Limit（每 IP 1h/次，每邮箱 24h/次）
 *   3. 临时邮箱域名黑名单
 */
import { EmailMessage } from 'cloudflare:email';
import protocol from '../../../misaka-protocol.json';
import {
  buildReplyText,
  detectIntakeType,
  extractLessonContent,
  parseEmailBody,
} from './email-utils.mjs';

// ── 临时邮箱域名黑名单（top 30） ──
const TEMP_EMAIL_DOMAINS = new Set([
  'mailinator.com', 'guerrillamail.com', '10minutemail.com',
  'tempmail.com', 'throwaway.email', 'yopmail.com',
  'sharklasers.com', 'trashmail.com', 'temp-mail.org',
  'mailnesia.com', 'dispostable.com', 'getnada.com',
  'burner.email', 'emailondeck.com', 'spamgourmet.com',
]);

// ── Turnstile 密钥 ──
// 从 env.TURNSTILE_SECRET 读取，不得硬编码在源码中

export default {
  async email(message, env, ctx) {
    const sender = message.from;
    const recipient = message.to;
    const subject = (message.headers.get('subject') || '').replace(/[\r\n]/g, ' ').trim();
    const messageId = (message.headers.get('message-id') || '').replace(/[\r\n]/g, ' ').trim();
    const domain = sender.split('@')[1]?.toLowerCase() || '';

    if (TEMP_EMAIL_DOMAINS.has(domain)) {
      console.log(`Blocked temp email: ${sender}`);
      return;
    }

    const lastReg = await env.MISAKANET_KV.get(`rate:email:${sender}`, 'text');
    if (lastReg && (Date.now() - parseInt(lastReg)) < 86400000) {
      console.log(`Rate limited email: ${sender}`);
      return;
    }
    await env.MISAKANET_KV.put(`rate:email:${sender}`, String(Date.now()), { expirationTtl: 86400 });

    // Consume the raw stream before forwarding and retain only bounded, plain text.
    const rawEmail = await new Response(message.raw).text();
    const emailBody = parseEmailBody(rawEmail);
    const lessonContent = extractLessonContent(emailBody);
    const intakeType = detectIntakeType(subject, lessonContent);
    const intakeId = crypto.randomUUID();
    const receivedAt = new Date().toISOString();
    let nodeId = await env.MISAKANET_KV.get(`email-node:${sender}`, 'text');

    // Every accepted sender receives a stable node ID, including lesson submitters.
    if (!nodeId) {
      const counter = await env.MISAKANET_KV.get('node_counter', 'text');
      const nextNum = (parseInt(counter) || 10052) + 1;
      nodeId = `Misaka${String(nextNum).padStart(5, '0')}`;
      await env.MISAKANET_KV.put('node_counter', String(nextNum));
      await env.MISAKANET_KV.put(`email-node:${sender}`, nodeId);
      const emailTier = protocol.registration?.email?.trust_tier ||
        Object.keys(protocol.trust_tiers || {}).find(k => protocol.trust_tiers[k].method === 'email') ||
        'mail-verified';
      await env.MISAKANET_KV.put(`node:${nodeId}`, JSON.stringify({
        nodeId, email: sender,
        registeredAt: receivedAt,
        source: 'email', trustLevel: emailTier,
        intakeId,
      }));
      console.log(`Registered via email: ${nodeId} <${sender}>`);
    }

    const intakeRecord = {
      intakeId,
      from: sender,
      to: recipient,
      subject,
      intakeType,
      lessonContent,
      nodeId,
      receivedAt,
      status: 'processed',
    };
    await env.MISAKANET_KV.put(
      `email-intake:${intakeId}`,
      JSON.stringify(intakeRecord),
      { expirationTtl: 2592000 },
    );
    console.log(`Intake ${intakeId}: ${intakeType} from ${sender} — "${subject}"`);

    if (env.GH_TOKEN) {
      try {
        intakeRecord.githubIssueUrl = await createAuditIssue(env, intakeRecord);
        await env.MISAKANET_KV.put(
          `email-intake:${intakeId}`,
          JSON.stringify(intakeRecord),
          { expirationTtl: 2592000 },
        );
        console.log(`Created audit issue: ${intakeRecord.githubIssueUrl}`);
      } catch (error) {
        console.error(`GitHub audit issue failed for ${intakeId}: ${error.message}`);
      }
    }

    const forwardHeaders = new Headers({
      'X-MisakaNet-Intake-Id': intakeId,
      'X-MisakaNet-Intake-Type': intakeType,
    });
    if (env.MAINTAINER_EMAIL) {
      await message.forward(env.MAINTAINER_EMAIL, forwardHeaders);
      console.log(`Forwarded ${intakeId} to ${env.MAINTAINER_EMAIL}`);
    } else {
      console.warn('MAINTAINER_EMAIL not configured — intake stored in KV only');
    }

    const reply = new EmailMessage(
      recipient,
      sender,
      [
        `From: MisakaNet <${recipient}>`,
        `To: ${sender}`,
        `Subject: Re: ${subject || 'MisakaNet email intake'}`,
        'Content-Type: text/plain; charset=UTF-8',
        ...(messageId ? [`In-Reply-To: ${messageId}`] : []),
        '',
        buildReplyText({ intakeId, intakeType, nodeId }),
      ].join('\r\n'),
    );
    await message.reply(reply);
    console.log(`Replied to ${sender} for intake ${intakeId}`);
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    const clientIP = request.headers.get('CF-Connecting-IP') || '';

    // ── POST /register — handle form submission ──
    if (url.pathname === '/register' && request.method === 'POST') {
      const form = await request.formData();
      const email = (form.get('email') || '').trim();
      const name = (form.get('name') || '').trim();
      const turnstileToken = (form.get('cf-turnstile-response') || '').trim();
      const domain = email.split('@')[1]?.toLowerCase() || '';

      // 防御 1: Turnstile 验证
      if (turnstileToken) {
        if (!env.TURNSTILE_SECRET) {
          return new Response(renderPage('error', 'Server configuration error: Turnstile secret not configured.'), {
            status: 500, headers: { 'Content-Type': 'text/html;charset=utf-8' }
          });
        }
        const verify = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
          method: 'POST',
          body: `secret=${env.TURNSTILE_SECRET}&response=${turnstileToken}`,
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        const outcome = await verify.json();
        if (!outcome.success) {
          return new Response(renderPage('error', 'Verification failed. Please try again.'), {
            status: 400, headers: { 'Content-Type': 'text/html;charset=utf-8' }
          });
        }
      } else {
        // 防御: 缺 Turnstile token → IP 限频（宽松）
        const ipCount = await env.MISAKANET_KV.get(`rate:ip:${clientIP}`, 'text');
        if (ipCount && (Date.now() - parseInt(ipCount)) < 3600000) {
          return new Response(renderPage('error', 'Too many registrations from this IP. Try again later.'), {
            status: 429, headers: { 'Content-Type': 'text/html;charset=utf-8' }
          });
        }
      }

      // 防御 2: 邮箱校验
      if (!email || !email.includes('@')) {
        return new Response(renderPage('error', 'Please enter a valid email address.'), {
          status: 400, headers: { 'Content-Type': 'text/html;charset=utf-8' }
        });
      }

      // 防御 3: 临时邮箱拦截
      if (TEMP_EMAIL_DOMAINS.has(domain)) {
        return new Response(renderPage('error', 'Temporary email addresses are not allowed.'), {
          status: 400, headers: { 'Content-Type': 'text/html;charset=utf-8' }
        });
      }

      // 防御 4: 每邮箱 24h 限频
      const lastReg = await env.MISAKANET_KV.get(`rate:email:${email}`, 'text');
      if (lastReg && (Date.now() - parseInt(lastReg)) < 86400000) {
        return new Response(renderPage('error', 'This email was already registered recently.'), {
          status: 429, headers: { 'Content-Type': 'text/html;charset=utf-8' }
        });
      }

      // ── 注册 ──
      await env.MISAKANET_KV.put(`rate:ip:${clientIP}`, String(Date.now()), { expirationTtl: 3600 });
      await env.MISAKANET_KV.put(`rate:email:${email}`, String(Date.now()), { expirationTtl: 86400 });

      const counter = await env.MISAKANET_KV.get('node_counter', 'text');
      const nextNum = (parseInt(counter) || 10052) + 1;
      const nodeId = `Misaka${String(nextNum).padStart(5, '0')}`;
      await env.MISAKANET_KV.put('node_counter', String(nextNum));
      const webTier = Object.keys(protocol.trust_tiers || {}).find(k => protocol.trust_tiers[k].method === 'web') || 
        'web-verified';
      await env.MISAKANET_KV.put(`node:${nodeId}`, JSON.stringify({
        nodeId, email, name,
        registeredAt: new Date().toISOString(),
        source: 'web', trustLevel: webTier
      }));

      return new Response(renderPage('success', { nodeId, email, name }), {
        status: 200, headers: { 'Content-Type': 'text/html;charset=utf-8' }
      });
    }

    // ── GET / — registration form ──
    return new Response(renderPage('form'), {
      status: 200,
      headers: { 'Content-Type': 'text/html;charset=utf-8' }
    });
  }
};

async function createAuditIssue(env, intake) {
  const repo = env.GH_REPO || 'Ikalus1988/MisakaNet';
  const labels = intake.intakeType === 'lesson-submission'
    ? ['lesson-intake']
    : ['registered', 'email'];
  const content = intake.lessonContent || '_No plain-text body was found._';
  const response = await fetch(`https://api.github.com/repos/${repo}/issues`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.GH_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json',
      'User-Agent': 'MisakaNet-email-intake',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    body: JSON.stringify({
      title: `[email/${intake.intakeType}] ${intake.subject || intake.intakeId}`.slice(0, 240),
      labels,
      body: [
        '<!-- Created automatically by the MisakaNet email intake Worker. -->',
        `- **Intake ID:** \`${intake.intakeId}\``,
        `- **Type:** \`${intake.intakeType}\``,
        `- **From:** \`${intake.from.replace(/`/g, '')}\``,
        `- **Received:** ${intake.receivedAt}`,
        intake.nodeId ? `- **Node ID:** \`${intake.nodeId}\`` : '',
        '',
        '## Parsed content',
        '',
        content.replace(/<!--/g, '&lt;!--').slice(0, 12000),
      ].filter(Boolean).join('\n'),
    }),
  });
  if (!response.ok) {
    throw new Error(`GitHub API ${response.status}: ${(await response.text()).slice(0, 300)}`);
  }
  return (await response.json()).html_url;
}

function renderPage(view, data) {
  const style = `
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:-apple-system,BlinkMacSystemFont,sans-serif; background:#0d1117; color:#c9d1d9; display:flex; align-items:center; justify-content:center; min-height:100vh; }
    .card { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:40px; width:100%; max-width:420px; }
    h1 { color:#58a6ff; font-size:20px; margin-bottom:8px; }
    p { color:#8b949e; font-size:14px; margin-bottom:24px; line-height:1.5; }
    label { display:block; font-size:13px; margin-bottom:4px; color:#8b949e; }
    input { width:100%; padding:10px 12px; background:#0d1117; border:1px solid #30363d; border-radius:6px; color:#c9d1d9; font-size:14px; margin-bottom:16px; outline:none; }
    input:focus { border-color:#58a6ff; }
    button { width:100%; padding:10px; background:#238636; border:none; border-radius:6px; color:#fff; font-size:14px; cursor:pointer; }
    button:hover { background:#2ea043; }
    .node-id { font-size:24px; font-weight:600; color:#58a6ff; text-align:center; padding:16px 0; }
    .badge { display:inline-block; background:#1f6feb22; color:#58a6ff; border:1px solid #1f6feb44; border-radius:4px; padding:2px 8px; font-size:12px; margin-bottom:16px; }
    .steps { font-size:13px; line-height:1.8; }
    .steps code { background:#0d1117; padding:2px 6px; border-radius:3px; font-size:12px; }
    .error { color:#f85149; background:#f8514911; border:1px solid #f8514944; padding:10px; border-radius:6px; font-size:13px; margin-bottom:16px; }
  `;

  if (view === 'form') {
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Register — MisakaNet</title>
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
    <style>${style}</style></head><body>
      <div class="card">
        <h1>Join the Swarm Knowledge Protocol</h1>
        <p>Get your node ID in under 5 seconds. No GitHub account needed.</p>
        <form method="POST" action="/register">
          <label for="email">Email address</label>
          <input type="email" id="email" name="email" placeholder="you@example.com" required autofocus>
          <label for="name">Node name (optional)</label>
          <input type="text" id="name" name="name" placeholder="my-agent">
          <div class="cf-turnstile" data-sitekey="0x4AAAAAADkC2fNcNsPpAKgf" style="margin-bottom:16px"></div>
          <button type="submit">🚀 Register</button>
        </form>
        <p style="margin-top:16px;font-size:12px;text-align:center">AI Agent? Email <code style="background:#0d1117;padding:1px 4px">bot@misakanet.org</code></p>
      </div>
    </body></html>`;
  }

  if (view === 'success') {
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Registered — MisakaNet</title><style>${style}</style></head><body>
      <div class="card">
        <div class="badge">✅ Registered</div>
        <h1>Welcome to the network</h1>
        <div class="node-id">${data.nodeId}</div>
        <p style="text-align:center;margin-bottom:20px">${data.email}${data.name ? ' · ' + data.name : ''}</p>
        <div class="steps">
          <b>Next steps:</b><br>
          1. <code>git clone https://github.com/Ikalus1988/MisakaNet.git</code><br>
          2. <code>pip install misakanet-core</code><br>
          3. <code>python3 search_knowledge.py "your problem"</code>
        </div>
        <p style="margin-top:20px;font-size:12px;color:#8b949e">"Every lesson learned once is never debugged again."</p>
      </div>
    </body></html>`;
  }

  if (view === 'error') {
    return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Error — MisakaNet</title><style>${style}</style></head><body>
      <div class="card">
        <h1>Registration failed</h1>
        <div class="error">${data}</div>
        <p><a href="/" style="color:#58a6ff">← Try again</a></p>
      </div>
    </body></html>`;
  }
}
