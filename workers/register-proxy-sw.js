--- a/workers/register-proxy-sw.js
+++ b/workers/register-proxy-sw.js
@@ -1138,6 +1138,56 @@
   return matches;
 };
 
+/**
+ * Search tokens against indexed FAQ/problem+answer rows using BM25 scoring.
+ * Returns rows sorted by score descending.
+ *
+ * @param {string[]} tokens
+ * @param {number} requiredOverlap minimum number of query tokens that must appear
+ * @param {Array<{title: string, problem: string, answer: string}>} rows
+ * @returns {{row: Object, score: number}[]}
+ */
+const matchTokens = (tokens, requiredOverlap, rows) => {
+  if (!rows || rows.length === 0) return [];
+
+  const termFreqs = rows.map((row) => {
+    const text = (row.title + " " + row.problem + " " + row.answer).toLowerCase();
+    const freq = {};
+    tokens.forEach((t) => {
+      freq[t] = (text.match(new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi")) || []).length;
+    });
+    return freq;
+  });
+
+  const docLens = rows.map((r) => (r.title + " " + r.problem + " " + r.answer).split(/\s+/).length);
+  const avgDocLen = docLens.reduce((a, b) => a + b, 0) / rows.length;
+
+  const results = rows.map((row, i) => {
+    let score = 0;
+    let overlap = 0;
+    tokens.forEach((t) => {
+      const tf = termFreqs[i][t] || 0;
+      if (tf > 0) {
+        overlap++;
+        const idf = Math.log(1 + (rows.length - tf + 0.5) / (tf + 0.5));
+        const dlFactor = docLens[i] / avgDocLen;
+        score += (tf * (idf + 1)) / (tf + 0.2 * dlFactor + 0.8);
+      }
+    });
+    return { row, score, overlap };
+  });
+
+  return results
+    .filter((r) => r.overlap >= requiredOverlap && r.score > 0)
+    .sort((a, b) => b.score - a.score)
+    .map((r) => ({ row: r.row, score: Math.round(r.score * 100) }));
+};
+
+const BM25_STOPWORDS = new Set([
+  "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
+  "of", "with", "by", "from", "as", "is", "are", "was", "were", "be",
+  "been", "being", "have", "has", "had", "do", "does", "did", "will",
+  "would", "could", "should", "may", "might", "can", "shall", "not",
+  "no", "nor", "so", "if", "then", "than", "too", "very", "just",
+  "about", "above", "after", "again", "all", "also", "am", "any",
+  "because", "before", "between", "both", "each", "few", "more",
+  "most", "other", "out", "over", "own", "same", "some", "such",
+  "through", "under", "until", "up", "into", "during", "only",
+]);
+
 const matchAnsweredQuestions = async (problem, answer, env, debugLog) => {
   const query = (problem + " " + answer).toLowerCase().replace(/[^\w\s]/g, " ").trim();
   const tokens = query.split(/\s+/).filter((t) => t.length > 0 && !BM25_STOPWORDS.has(t));
@@ -1179,6 +1229,47 @@
   return answers;
 };
 
+/**
+ * Fetch answered FAQ questions from D1.
+ * Returns an object with status, count, and rows so callers can distinguish
+ * read failures from genuinely empty results.
+ *
+ * @param {object} env
+ * @param {Function} debugLog
+ * @returns {{status: 'ok'|'error', count: number, rows: Array<{title:string,problem:string,answer:string}>, message?: string}}
+ */
+const fetchAnsweredQuestions = async (env, debugLog) => {
+  try {
+    const sql = `SELECT problem, answer FROM answered_questions WHERE blocked = 0 ORDER BY created_at DESC LIMIT 50`;
+    const { results } = await env.DB.prepare(sql).all();
+    const rows = (results || []).map((r) => ({
+      title: r.problem.slice(0, 120),
+      problem: r.problem,
+      answer: r.answer,
+    }));
+    debugLog(env, 2, `fetchAnsweredQuestions ok: ${rows.length} rows`);
+    return { status: "ok", count: rows.length, rows };
+  } catch (e) {
+    const msg = String(e && e.message || e);
+    debugLog(env, 1, "fetchAnsweredQuestions failed", msg);
+    return { status: "error", count: 0, rows: [], message: msg };
+  }
+};
+
+/**
+ * Match answered FAQ questions against a problem+answer query.
+ * Distinguishes retrieval errors from true no-match so callers can surface
+ * diagnostics instead of silently returning no_match: true.
+ *
+ * @param {string} problem
+ * @param {string} answer
+ * @param {object} env
+ * @param {Function} debugLog
+ * @returns {{answers: Array<{title:string, score:number}>, error?: string, hint?: string}}
+ */
+const matchAnsweredQuestions = async (problem, answer, env, debugLog) => {
+  const query = (problem + " " + answer).toLowerCase().replace(/[^\w\s]/g, " ").trim();
+  const tokens = query.split(/\s+/).filter((t) => t.length > 0 && !BM25_STOPWORDS.has(t));
+  const fetchResult = await fetchAnsweredQuestions(env, debugLog);
+
+  if (fetchResult.status === "error") {
+    debugLog(env, 1, "matchAnsweredQuestions: D1 fetch error, tokens=", tokens.join(","), " rows=", fetchResult.rows.length, " message=", fetchResult.message);
+    return { answers: [], error: "D1 read failure: " + fetchResult.message, hint: "检索后端读取失败，非知识库缺失" };
+  }
+
+  const matches = matchTokens(tokens, Math.max(1, Math.ceil(tokens.length * 0.4)), fetchResult.rows);
+  debugLog(env, 2, "matchAnsweredQuestions: tokens=", tokens.join(","), " requiredOverlap=", Math.max(1, Math.ceil(tokens.length * 0.4)), " overlap=", matches.length > 0 ? matches[0].overlap : "n/a", " rowsScanned=", fetchResult.rows.length);
+
+  const answers = matches.map((m) => ({ title: m.row.title, score: m.score }));
+  return { answers, error: null, hint: fetchResult.rows.length === 0 ? "FAQ 库为空" : null };
+};
+
 const fetchCourses = async (env, debugLog) => {
   const sql = `SELECT * FROM courses ORDER BY created_at DESC LIMIT 50`;
   const result = await env.DB.prepare(sql).run();
@@ -1220,34 +1311,6 @@
   return result;
 };
 
-const matchTokens = (tokens, requiredOverlap, rows) => {
-  const results = rows.map((row, i) => {
-    const text = (row.title + " " + row.problem + " " + row.answer).toLowerCase();
-    let score = 0;
-    let overlap = 0;
-    tokens.forEach((t) => {
-      const regex = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
-      const matches = text.match(regex);
-      if (matches) {
-        overlap++;
-        const tf = matches.length;
-        const idf = Math.log(1 + (rows.length - tf + 0.5) / (tf + 0.5));
-        const dlFactor = (row.title + " " + row.problem + " " + row.answer).split(/\s+/).length / (rows.reduce((sum, r) => sum + (r.title + " " + r.problem + " " + r.answer).split(/\s+/).length, 0) / rows.length);
-        score += (tf * (idf + 1)) / (tf + 0.2 * dlFactor + 0.8);
-      }
-    });
-    return { row, score, overlap };
-  });
-  return results.filter((r) => r.overlap >= requiredOverlap && r.score > 0).sort((a, b) => b.score - a.score).map((r) => ({ row: r.row, score: Math.round(r.score * 100) }));
-};
-
-const BM25_STOPWORDS = new Set(["a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "from", "as", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "shall", "not", "no", "nor", "so", "if", "then", "than", "too", "very", "just", "about", "above", "after", "again", "all", "also", "am", "any", "because", "before", "between", "both", "each", "few", "more", "most", "other", "out", "over", "own", "same", "some", "such", "through", "under", "until", "up", "into", "during", "only"]);
-
-const matchAnsweredQuestions = async (problem, answer, env, debugLog) => {
-  const query = (problem + " " + answer).toLowerCase().replace(/[^\w\s]/g, " ").trim();
-  const tokens = query.split(/\s+/).filter((t) => t.length > 0 && !BM25_STOPWORDS.has(t));
-  debugLog(env, 2, "matching", tokens, "against", (await env.DB.prepare("SELECT problem, answer FROM answered_questions WHERE blocked = 0").all()).results?.length || 0, "rows");
-  const matches = matchTokens(tokens, Math.max(1, Math.ceil(tokens.length * 0.4)), (await env.DB.prepare("SELECT problem, answer FROM answered_questions WHERE blocked = 0 ORDER BY created_at DESC LIMIT 50").all()).results?.map(r => ({ title: r.problem.slice(0, 120), problem: r.problem, answer: r.answer })) || []);
-  return matches.map(m => ({ title: m.row.title, score: m.score }));
-};
-
 const handleMCPToolCall = async (toolName, args, env, debugLog) => {
   if (toolName === "addCourse") {
     const { courseUrl, courseName, courseDescription } = args;
@@ -1267,10 +1330,17 @@
     const { problem, answer } = args;
     if (!problem) throw new Error("问题内容不能为空");
     const questions = await matchAnsweredQuestions(problem, answer, env, debugLog);
-    if (questions.length > 0) return { found: true, questions };
-    const existing = await checkDuplicateCourse(env, debugLog, problem, answer);
-    if (existing.exists) return { found: false, questions: [], duplicate: true };
-    return { found: false, questions: [], duplicate: false };
+    if (questions.error) {
+      // Retrieval error — surface it instead of pretending the knowledge doesn't exist.
+      debugLog(env, 1, "matchAnsweredQuestions returned error:", questions.error);
+      return { found: false, questions: [], duplicate: false, retrievalError: questions.error, hint: questions.hint };
+    }
+    if (questions.answers.length > 0) return { found: true, questions: questions.answers };
+    const existing = await checkDuplicateCourse(env, debugLog, problem, answer);
+    if (existing.exists) return { found: false, questions: [], duplicate: true };
+    if (questions.hint) {
+      debugLog(env, 2, "matchAnsweredQuestions hint:", questions.hint);
+    }
+    return { found: false, questions: [], duplicate: false };
   },
   listQuestions: async (args, env, debugLog) => {
     const questions = await listAnsweredQuestions(env, debugLog);
@@ -1335,7 +1405,9 @@
         answer,
         type,
         env,
-        debugLog
+        debugLog,
+        "addQuestion"
       );
       if (existing.exists) {
         return jsonErrorResponse(409, "问题已存在", "该问题已在知识库中，请勿重复添加", env);
@@ -1348,7 +1420,7 @@
   handleMCPToolCall(name, args, env, debugLog, operationName);
 };
 
-const matchCourses = async (query, env, debugLog) => {
+const matchCourses = async (query, env, debugLog, operationName) => {
   const q = query.toLowerCase().replace(/[^\w\s]/g, " ").trim();
   const tokens = q.split(/\s+/).filter((t) => t.length > 0 && !COURSE_STOPWORDS.has(t));
   debugLog(env, 2, "Searching courses", tokens);
@@ -1387,7 +1459,7 @@
   let answered = [];
   if (query.length > 0 && !isProblemUrl(query) && !isCourseUrl(query)) {
     try {
-      answered = (await matchAnsweredQuestions(query, "", env, debugLog)).slice(0, 3);
+      answered = (await matchAnsweredQuestions(query, "", env, debugLog, "search")).slice(0, 3);
     } catch (e) {
       debugLog(env, 1, "matchAnsweredQuestions search error:", String(e && e.message || e));
     }
@@ -1415,7 +1487,8 @@
     searchResults.push(...answered.map((a, i) => ({
       type: "faq",
       index: coursesStartIndex + i,
-      content: { ...a, source: "faq" }
+      content: { ...a, source: "faq" },
+      retrievalError: a.retrievalError || null,
     })));
 
     // Check if any search result is a URL
@@ -1472,6 +1545,14 @@
           return;
         }
       }
+      // If we got a retrieval error from FAQ search, log it and don't silently return no_match.
+      if (searchResults.some(r => r.retrievalError)) {
+        debugLog(env, 1, "search: FAQ retrieval error detected, results may be incomplete. errors:",
+          searchResults.filter(r => r.retrievalError).map(r => r.retrievalError));
+        return;
+      }
+    } catch (e) {
+      debugLog(env, 1, "search catch error:", String(e && e.message || e));
     }
 
     // If we get here with no results, try to find the closest course by name
@@ -2371,7 +2452,7 @@
   return {
     addCourse: {
       description: "Add a new course to the database.",
-      input_schema: {
+      inputSchema: {
         type: "object",
         properties: {
           courseUrl: { type: "string", description: "Course URL (e.g. https://github.com/...)" },
@@ -2381,7 +2462,7 @@
     },
     addQuestion: {
       description: "Add a new question/answer pair to the knowledge base.",
-      input_schema: {
+      inputSchema: {
         type: "object",
         properties: {
           problem: { type: "string", description: "The problem description" },
@@ -2391,7 +2472,7 @@
     },
     search: {
       description: "Search for courses and FAQs based on a query.",
-      input_schema: {
+      inputSchema: {
         type: "object",
         properties: {
           query: { type: "string", description: "Search query" },
>>>ENDFILE>>>
