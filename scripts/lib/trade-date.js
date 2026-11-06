// Trading-day resolution for the after-close collection job.
//
// The local daily-k files are only updated by the official data updater, which
// runs after the collection job. Using their newest date as "today" therefore
// makes the job collect the previous trading day. The market server is the
// source of truth; local files are only a fallback.

const DEFAULT_SYMBOLS = ['sh000001'];
const DEFAULT_BAR_COUNT = 5;

function normalizeDate(value) {
  if (value === null || value === undefined) return null;
  const digits = String(value).replace(/\D/g, '').slice(0, 8);
  return digits.length === 8 ? digits : null;
}

function maxDate(dates) {
  let best = null;
  for (const d of dates) {
    const n = normalizeDate(d);
    if (n && (best === null || n > best)) best = n;
  }
  return best;
}

/**
 * Resolve the current trading day.
 *
 * @param {object} options
 * @param {(symbol: string, count: number) => Promise<Array<{date: string|number}>>} [options.fetchBars]
 *   Fetches the latest daily bars for a symbol from the quote server.
 * @param {string[]} [options.symbols] Index / leader-stock symbols to query.
 * @param {number} [options.barCount] Number of recent bars to request per symbol.
 * @param {() => (string|number|null|Promise<string|number|null>)} [options.getLocalLatestDate]
 *   Returns the newest date found in the local daily-k files (fallback only).
 * @returns {Promise<{date: string|null, source: 'remote'|'local'|'none'}>}
 */
export async function resolveTradeDate(options = {}) {
  const {
    fetchBars,
    symbols = DEFAULT_SYMBOLS,
    barCount = DEFAULT_BAR_COUNT,
    getLocalLatestDate,
  } = options;

  if (typeof fetchBars === 'function') {
    const results = await Promise.all(
      symbols.map(async (symbol) => {
        try {
          const bars = await fetchBars(symbol, barCount);
          return Array.isArray(bars) ? bars.map((bar) => bar && bar.date) : [];
        } catch (_) {
          return [];
        }
      }),
    );
    const remote = maxDate(results.flat());
    if (remote) return { date: remote, source: 'remote' };
  }

  if (typeof getLocalLatestDate === 'function') {
    const local = normalizeDate(await getLocalLatestDate());
    if (local) return { date: local, source: 'local' };
  }

  return { date: null, source: 'none' };
}

/**
 * Describe daily-k coverage for the trading day. A short count is advisory
 * (the updater may simply not have run yet), so this returns a log line
 * instead of throwing.
 *
 * @returns {{ok: boolean, message: string}}
 */
export function describeKlineCoverage({ date, count, expected }) {
  if (expected > 0 && count < expected) {
    return {
      ok: false,
      message: `日k ${date} 当日条数不足 (${count}/${expected})，继续采集`,
    };
  }
  return { ok: true, message: `日k ${date} 当日条数 ${count}` };
}
