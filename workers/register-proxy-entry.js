/**
 * The Worker's entry point — and the only module the runtime ever sees.
 *
 * **Why this file exists.** `register-proxy-sw.js` exports 130 names, because the 94 worker test
 * files reach the helpers they assert against through them. Forty-four of those 130 are
 * constants, and workerd builds a map of the **entry** module's exports when it starts the
 * Worker: every entry in that map must be a function or an `ExportedHandler`, or the Worker
 * refuses to start.
 *
 *     Uncaught TypeError: Incorrect type for map entry 'ACTIVITY_CACHE_CONTROL':
 *     the provided value is not of type 'function or ExportedHandler'.
 *
 * The rule is about the *entry*, not about the module. An imported module's exports are ordinary
 * ES module exports and are not restricted — a Worker whose entry only exports `default` starts
 * with an imported module full of constants. So the implementation stays where the tests reach
 * it, and this file is what the runtime loads: the default handler, and nothing else.
 *
 * **What it cost to not have it.** `wrangler dev` on this Worker failed at startup every single
 * time, so the Worker could not be run locally at all — the one thing a Worker is run locally for.
 * It was invisible in CI because the worker tests import the implementation module directly, and
 * Node has no such rule: a constant is a perfectly good export there. A Worker that cannot start
 * and a Worker that works looked identical to every gate in this repository.
 *
 * `tests/test_worker_entry_exports.py` is the gate that says so. It reads the entry out of
 * `workers/wrangler.toml`, so moving the entry moves the gate with it.
 */
import handler from './register-proxy-sw.js';

export default handler;
