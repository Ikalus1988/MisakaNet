// Unit tests for the public lesson coverage dashboard (Issue #905).
import assert from 'node:assert/strict';
import test from 'node:test';

import worker, {
  buildLessonCoverage,
  handleLessonCoverage,
} from './register-proxy-sw.js';

const LESSONS = [
  { id: 'python-pip', title: 'Python pip timeout recovery', domain: 'devops', tags: ['pip', 'venv'], status: 'published' },
  { id: 'github-auth', title: 'GitHub token 401 recovery', domain: 'devops', tags: ['github', 'token'], status: 'published' },
  { id: 'draft-docker', title: 'Docker draft', domain: 'devops', tags: ['docker'], status: 'draft' },
];

const SIGNALS = {
  families: [
    { taskFamily: 'python-env', unsolved7d: 2, unsolved30d: 3, lastSeen: '2026-08-13' },
  ],
  staleLessons: [{ lessonId: 'python-pip', notHelpful30d: 2, lastSeen: '2026-08-12' }],
};

test('coverage classifies covered, review, and uncovered families', () => {
  const report = buildLessonCoverage(LESSONS, SIGNALS);
  assert.equal(report.metrics.totalLessons, 3);
  assert.equal(report.metrics.publishedLessons, 2);
  assert.equal(report.metrics.coveredFamilies, 2);
  assert.equal(report.metrics.coveragePercent, 16.7);
  assert.equal(report.metrics.gapCount, 11);

  const python = report.families.find((family) => family.taskFamily === 'python-env');
  assert.equal(python.coverageStatus, 'needs-review');
  assert.equal(python.lessonCount, 1);
  assert.equal(python.unsolved30d, 3);

  const glama = report.families.find((family) => family.taskFamily === 'glama-release');
  assert.equal(glama.coverageStatus, 'uncovered');
  assert.ok(report.gaps.some((family) => family.taskFamily === 'glama-release'));
});

test('handler returns valid JSON with explicit privacy metadata', async () => {
  const response = await handleLessonCoverage({
    LESSON_DATA: LESSONS,
    UNSOLVED_DATA: SIGNALS,
  });
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.success, true);
  assert.equal(body.meta.lessonSource, 'data/lessons.json');
  assert.equal(body.meta.raw_query, false);
  assert.equal(body.meta.pii, false);
  assert.equal(body.staleLessons[0].lessonId, 'python-pip');
});

test('public worker route works without REGISTER_TOKEN or KV', async () => {
  const response = await worker.fetch(
    new Request('https://misakanet.org/api/insights/lesson-coverage'),
    { LESSON_DATA: LESSONS, UNSOLVED_DATA: SIGNALS },
  );
  assert.equal(response.status, 200);
});
