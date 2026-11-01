// The MCP intake classifier, as a module the workflow requires and the test imports.
//
// Why it is a file and not inline `script:` (2026-11-01)
// -----------------------------------------------------
// The logic lived inline in `.github/workflows/issue-intake-triage.yml`, which meant the only way
// to exercise it was to read the YAML, pull the string out, and compile that string into a function
// — a test that built a program out of text. Two code-scanning alerts (#386/#387,
// `DANGEROUS_DYNAMIC_EXECUTION`) were the honest response to that shape, and the alternative was
// dismissing them in a scanner so the pattern could come back somewhere it matters.
//
// So: the classifier is a CommonJS module. The workflow checks the repository out and `require`s
// it; the test does the same with `github`/`core`/`context` stubs. No string is ever evaluated, the
// file is analysable by every scanner, and the test imports the same code the workflow runs instead
// of a copy of its text.
//
// `require` rather than `import`: `.cjs` because the repository's `package.json` sets
// `"type": "module"`, and `actions/github-script` hands the script a CommonJS-ish scope where
// `require()` resolves against the checked-out workspace.
'use strict';

/**
 * Classify one MCP intake issue and reconcile its labels.
 *
 * @param {object} deps
 * @param {object} deps.github   the `@actions/github` client (rest + paginate)
 * @param {object} deps.core     the `@actions/core` logging/failure channel
 * @param {object} deps.context  the workflow context (repo, issue, payload)
 * @returns {Promise<void>}
 */
module.exports = async function classifyIntake({ github, core, context }) {
  const owner = context.repo.owner;
  const repo = context.repo.repo;
  let issue = context.payload.issue;
  let issue_number = context.issue?.number;
  if (!issue || !issue_number) {
    const input = process.env.ISSUE_NUMBER || '';
    issue_number = Number(input);
    if (!issue_number || isNaN(issue_number)) {
      core.setFailed(`Invalid issue number: "${input}"`);
      return;
    }
    const response = await github.rest.issues.get({ owner, repo, issue_number });
    issue = response.data;
  }
  const title = issue.title || '';
  const body = issue.body || '';
  const labelNames = new Set((issue.labels || []).map((label) => label.name));

  const isIntake =
    labelNames.has('intake') ||
    labelNames.has('mcp-intake') ||
    title.startsWith('[Intake]') ||
    /Submitted via remote MCP/i.test(body);

  if (!isIntake) {
    core.info(`Issue #${issue_number} is not an MCP intake; skipping.`);
    return;
  }

  const source = (body.match(/\*\*Source:\*\*\s*([^\n]+)/i)?.[1] || '').trim();
  const kind = (body.match(/\*\*Kind:\*\*\s*([^\n]+)/i)?.[1] || '').trim();
  const dedup = (body.match(/\*\*Dedup:\*\*\s*`?([^`\n]+)`?/i)?.[1] || '').trim();
  // GitHub/Opire append boilerplate (rewards footer, etc.) full of
  // English words ("add", "documentation", "what") that corrupt the
  // keyword type detection below (observed on #1396 → spurious
  // type:feature). Scan only the submitter-authored text.
  const text = `${title}\n${body}`.replace(/<details>[\s\S]*?<\/details>/gi, ' ');
  const kindLower = kind.toLowerCase();

  const isTest = /heartbeat-verify|heartbeat verify|session-test/i.test(text) || /heartbeat|session-test/i.test(source);
  const isHarvestedAgentSkill = /harvested from local lesson skill-|Hermes Agent/i.test(text);
  // A proposal announces itself one of two ways. `kind=proposal` is the structured one
  // (it exists because of #4251 — a three-month plan had to be filed as
  // `new_lesson_candidate` and then argue in prose that it was not a failure report);
  // the prose declaration is what a client that only knows the four older kinds can
  // still do, and it stays supported on purpose. Guessing the class from topic words is
  // what labelled #4251 `type:bug` — the plan *discusses* failures — so neither path
  // reads the subject, and neither is a "sounds like a plan" heuristic.
  const declaresNotAFailureReport =
    /\bnot a failure report\b|\bnon[- ]failure report\b|\(proposal\)|\btriage it as (?:such|a proposal)\b|\bthis is a proposal\b/i.test(text);
  const isProposal = kindLower === 'proposal' || declaresNotAFailureReport;
  const hasProblem = /##\s+Problem/i.test(body);
  const hasVerification = /##\s+Verification/i.test(body);
  const hasFix = /##\s+Fix/i.test(body);
  const hasTried = /##\s+What was tried/i.test(body);
  const hasCoreStructure = hasProblem && hasVerification && (hasFix || hasTried);

  // ── Issue type detection ──
  // The structured Kind field (from MCP submit_intake / pipeline)
  // wins: a kind=question intake must never be re-labeled
  // feature/bug by keyword noise.
  const isBug = /\b(error|crash|fail|bug|broken|exception|traceback|segfault)\b/i.test(text);
  const isFeature = /\b(feature|enhancement|add|support|implement|improve|new)\b/i.test(text);
  const isQuestion = (/\b(how|why|what|question|help|docs|documentation)\b/i.test(text) && !isBug) || kindLower === 'question';

  let issueType = 'unknown';
  if (kindLower === 'question') issueType = 'question';
  else if (isProposal) issueType = 'feature';
  else if (isBug) issueType = 'bug';
  else if (isFeature) issueType = 'feature';
  else if (isQuestion) issueType = 'question';

  // ── Priority scoring (0-100) ──
  let priorityScore = 50; // baseline
  // Structure bonus
  if (hasCoreStructure) priorityScore += 15;
  if (hasProblem) priorityScore += 5;
  if (hasFix) priorityScore += 5;
  if (hasVerification) priorityScore += 5;
  if (hasTried) priorityScore += 5;
  // Content quality
  const wordCount = body.split(/\s+/).length;
  if (wordCount >= 100) priorityScore += 10;
  else if (wordCount >= 50) priorityScore += 5;
  // Code/error evidence
  if (/```/.test(body)) priorityScore += 5;
  if (/Error:|Traceback|Exception|ENOENT|EACCES|404|500/i.test(body)) priorityScore += 5;
  // Source bonus
  if (source && !isTest) priorityScore += 5;
  // Penalties
  if (isTest) priorityScore -= 30;
  if (wordCount < 20) priorityScore -= 20;
  if (!hasProblem && !hasFix) priorityScore -= 15;
  // Clamp
  priorityScore = Math.max(0, Math.min(100, priorityScore));

  let priorityLabel = 'priority:low';
  if (priorityScore >= 80) priorityLabel = 'priority:high';
  else if (priorityScore >= 60) priorityLabel = 'priority:medium';

  let classification = 'lesson-candidate';
  let suggestedAction = 'Review manually. Convert to a formal lesson if the failure, fix, and verification are concrete; otherwise ask for details or close.';
  const labelsToAdd = ['intake', 'mcp-intake', 'pending-review', 'needs-human-review'];
  // Labels the fresh classification contradicts, removed on re-triage. The question
  // branch has always done this; the proposal branch needs it because #4251 already
  // carries `type:bug` and `pending-review` from its first, wrong pass.
  const labelsToRemove = [];

  if (kindLower === 'question') {
    // Question / knowledge-gap intake — NOT a lesson candidate.
    // Route to question handling: ask the submitter for the concrete
    // error, what was tried, and the expected outcome; keep open as a
    // question/FAQ until it gains a failure+fix+verification shape.
    classification = 'question';
    suggestedAction = 'Question / knowledge-gap intake (not a lesson candidate). Ask the submitter for the concrete error, what was tried, and the expected outcome. Convert to a lesson only if it gains a failure + fix + verification shape; otherwise answer, keep as an open question, or close as a duplicate.';
    labelsToAdd.push('question');
    labelsToRemove.push('auto-rejected', 'needs-salvage', 'type:feature', 'type:bug');
  } else if (isProposal) {
    // A proposal / product request: not lesson material, not a bug, and not waiting to
    // be reviewed as a lesson. Its exit is a decision plus, if accepted, issues that
    // name the file or the gate each change touches — so `pending-review` and the
    // bug-keyword type both have to come off rather than sit there meaning nothing.
    classification = 'proposal';
    suggestedAction = 'Proposal / product request — not a failure report, so there is no lesson to convert. Decide accept or decline. If accepted, split it into issues that each name the file, workflow or gate they change, and cite the measurement behind each target; if declined, say what the proposal assumes that the repository does not hold. Nothing here rides on a benchmark score alone.';
    // Out of the *add* set too, not just off the issue: dropping it only from
    // `labelsToRemove` meant a first-time proposal got `pending-review` applied (the
    // removal pass checks the label snapshot taken before the add), and on #4251 the
    // label happened to pre-exist, which is why the live re-triage looked right.
    labelsToAdd.splice(labelsToAdd.indexOf('pending-review'), 1);
    labelsToRemove.push('pending-review', 'type:bug');
  } else if (isTest) {
    classification = 'intake-test';
    suggestedAction = 'Verify the transport path, then close as a test intake. Do not convert to a lesson unless it captures a reusable failure pattern.';
    labelsToAdd.push('test');
  } else if (isHarvestedAgentSkill) {
    classification = 'harvested-agent-skill';
    suggestedAction = 'Batch review with related harvested skill intakes. Convert only if it contains a concrete failure/recovery pattern; close vague module summaries.';
    labelsToAdd.push('agent-friendly');
  }

  // `needs-ac` means "the failure report lacks acceptance criteria". A proposal is not
  // a report, so the rule does not apply to it and the label would be noise.
  if (!hasCoreStructure && classification !== 'proposal') {
    labelsToAdd.push('needs-ac');
  }

  // Add priority and type labels
  labelsToAdd.push(priorityLabel);
  if (issueType !== 'unknown') {
    labelsToAdd.push(`type:${issueType}`);
  }

  const missingLabels = [...new Set(labelsToAdd)].filter((label) => !labelNames.has(label));
  if (missingLabels.length > 0) {
    await github.rest.issues.addLabels({ owner, repo, issue_number, labels: missingLabels });
    core.info(`Added labels: ${missingLabels.join(', ')}`);
  } else {
    core.info('No labels to add.');
  }

  // Reconcile labels that contradict the fresh classification. A question intake is
  // neither a lesson failure case (auto-rejected/needs-salvage) nor a feature/bug
  // (spurious keyword hits); a proposal is not awaiting lesson review and is not a bug.
  // Anything the branch above listed comes off here.
  for (const label of labelsToRemove) {
    if (labelNames.has(label)) {
      await github.rest.issues.removeLabel({ owner, repo, issue_number, name: label });
      core.info(`Removed stale label: ${label}`);
    }
  }

  const marker = '<!-- misakanet-intake-triage -->';
  const comments = await github.paginate(github.rest.issues.listComments, {
    owner,
    repo,
    issue_number,
    per_page: 100,
  });
  // "Already commented" is not the same question as "already said *this*". The guard used
  // to be the marker alone, so a rule change re-labelled the issue while the comment above
  // it kept saying the old thing — observed on #4251 an hour after its proposal branch
  // landed: labels went `lesson-candidate`/`type:bug` → `proposal`/`type:feature` and the
  // comment did not move. Compare the classification line, not the marker, so a
  // re-triage that changes its mind says so.
  const previous = comments
    .filter((comment) => comment.body && comment.body.includes(marker))
    .map((comment) => (comment.body.match(/- Classification: `([^`]+)`/) || [])[1])
    .filter(Boolean);
  const lastClassification = previous.length ? previous[previous.length - 1] : null;
  if (lastClassification === classification) {
    core.info(`Triage comment already says ${classification}; skipping comment.`);
    return;
  }

  const checklist = [
    marker,
    '## MCP Intake Triage',
    '',
    ...(lastClassification ? [`- Re-triaged: classification changed from \`${lastClassification}\` to \`${classification}\`; the labels were reconciled.`] : []),
    `- Classification: \`${classification}\``,
    `- Issue type: \`${issueType}\``,
    `- Priority: \`${priorityLabel}\` (score: ${priorityScore}/100)`,
    `- Kind: \`${kind || 'unknown'}\``,
    `- Source: \`${source || 'unknown'}\``,
    `- Dedup: \`${dedup || 'missing'}\``,
    `- Core structure: ${hasCoreStructure ? 'present' : 'incomplete'}`,
    '',
    '### Suggested maintainer action',
    '',
    suggestedAction,
    '',
    '### Review checklist',
    '',
    '- [ ] Confirm no secrets, internal URLs, or personal data remain.',
    '- [ ] Search existing lessons for duplicates using the dedup hash and topic.',
    '- [ ] Decide: convert to lesson / answer as a question / ask for more detail / close as duplicate, test, or vague intake.',
    '',
    '_Automated triage only. This does not publish lessons or close issues._',
  ].join('\n');

  await github.rest.issues.createComment({ owner, repo, issue_number, body: checklist });
  core.info(`Posted triage comment for ${classification}.`);
};
