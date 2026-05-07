/**
 * service-logger.js
 *
 * Shared logging helper for all participant services.
 *
 * WHY THIS EXISTS:
 *   logFailure was copy-pasted identically into admin.service.js,
 *   join.service.js, and leave.service.js.  Three identical copies mean
 *   three places to update if the logger interface or log format ever
 *   changes.  This module is the single source of truth.
 *
 * BEHAVIOUR:
 *   - Expected operational errors (AppError / 4xx) → logger.warn
 *     These are normal application flow events (404 not found, 409 conflict,
 *     403 forbidden) and should not page an on-call engineer.
 *   - Unexpected runtime errors → logger.error
 *     These are genuine failures that need investigation.
 */

const AppError = require('../utils/AppError');
const logger   = require('../utils/logger');

/**
 * Log a service-layer failure at the appropriate severity level.
 *
 * @param {string} event – structured log event name, e.g. 'trackJoin_failed'
 * @param {object} ctx   – arbitrary context fields (requestId, meetingId, …)
 * @param {Error}  err   – the caught error
 */
function logFailure(event, ctx, err) {
  const logFn = err instanceof AppError ? logger.warn : logger.error;
  logFn.call(logger, event, { ...ctx, error: err });
}

module.exports = { logFailure };
