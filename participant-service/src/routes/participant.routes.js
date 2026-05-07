/**
 * Participant Routes
 *
 * Layered Throttling Architecture
 * ────────────────────────────────
 *  globalLimiter  200 req / 15 min  – DDoS / abuse circuit-breaker for the whole layer
 *  readLimiter    120 req / 15 min  – ceiling for polling / listing requests
 *  writeLimiter    20 req / 15 min  – tight limit on state-mutating operations
 *
 * FIX: The previous globalLimiter was set to 100 req/15 min while readLimiter
 * was 120.  Because globalLimiter applies to ALL routes via router.use(), it
 * triggered at 100 requests before readLimiter ever had a chance to fire at 120,
 * making readLimiter completely dead code on the list route.
 *
 * Fix: globalLimiter is now 200 — high enough to act only as a DDoS
 * circuit-breaker without interfering with per-endpoint limits.
 * Effective per-user ceilings:
 *   - List (GET)         120 / 15 min  (readLimiter)
 *   - Mutations (writes)  20 / 15 min  (writeLimiter)
 *   - Any single key    200 / 15 min  (globalLimiter abuse guard)
 *
 * Rate-limit keys are resolved in priority order:
 *   1. Authenticated user ID        (most stable / accurate)
 *   2. Guest participant ID         (stable within a session)
 *   3. IP address                   (fallback for unauthenticated callers)
 *   4. UA + Accept-Language hash    (last-resort; easily spoofed — document
 *                                    this limitation in the runbook)
 *
 * Middleware order per route:
 *   authGuard → globalLimiter → [writeLimiter | readLimiter] → validateParams
 *     → [requireJson] → [validate(body)] → [roleGuard] → controller
 *
 * roleGuard is intentionally absent from /join, /leave, and /wait because
 * those are self-service endpoints: ownership is enforced inside the service
 * layer via verifyParticipantOwnership.
 */

const express = require('express');
const crypto  = require('crypto');
const { Router }    = express;
const rateLimit     = require('express-rate-limit');
const { ParticipantController } = require('../controllers/participant.controller');
const { authGuard, roleGuard }  = require('../middlewares/auth.middleware');
const { validate, validateParams } = require('../middlewares/validate.middleware');
const { requireJson }           = require('../middlewares/contentType.middleware');
const {
  inviteSchema,
  meetingParamSchema,
  participantParamSchema,
} = require('../validators/participant.validator');

const router = Router();

/* ------------------------------------------------------------------ */
/*  Rate-limit key resolver                                             */
/* ------------------------------------------------------------------ */
function getRateLimitKey(req) {
  if (req.user?.id)                 return `user:${req.user.id}`;
  if (req.user?.guestParticipantId) return `guest:${req.user.guestParticipantId}`;
  if (req.ip)                       return `ip:${req.ip}`;

  // Last-resort fingerprint – easily spoofed; use only as a rough circuit-breaker.
  const raw  = (req.headers['user-agent'] ?? '') + (req.headers['accept-language'] ?? '');
  const hash = crypto.createHash('sha256').update(raw).digest('hex').slice(0, 16);
  return `fp:${hash || 'anonymous'}`;
}

const rateLimitHandler = (_req, res) =>
  res.status(429).json({ success: false, message: 'Too many requests, please slow down.' });

/* ------------------------------------------------------------------ */
/*  Limiters                                                            */
/* ------------------------------------------------------------------ */
const sharedLimiterOptions = {
  windowMs:     15 * 60 * 1000,
  keyGenerator: getRateLimitKey,
  handler:      rateLimitHandler,
  // Suppress X-Forwarded-For warning only — all other validations remain active.
  // We use a custom keyGenerator that does not rely on X-Forwarded-For, but
  // we still want the trust-proxy and store-connection checks.
  validate:     { xForwardedForHeader: false },
};

const globalLimiter = rateLimit({ ...sharedLimiterOptions, max: 200 }); // abuse guard
const readLimiter   = rateLimit({ ...sharedLimiterOptions, max: 120 }); // list ceiling
const writeLimiter  = rateLimit({ ...sharedLimiterOptions, max: 20  }); // mutation ceiling

/* ------------------------------------------------------------------ */
/*  Route definitions                                                   */
/* ------------------------------------------------------------------ */
router.use(authGuard);
router.use(globalLimiter);

// ── Host / co-host mutations ──────────────────────────────────────────
router.post(
  '/:meetingId/participants/invite',
  writeLimiter,
  validateParams(meetingParamSchema),
  requireJson,
  validate(inviteSchema),
  roleGuard,
  ParticipantController.invite,
);

router.delete(
  '/:meetingId/participants/:participantId',
  writeLimiter,
  validateParams(participantParamSchema),
  roleGuard,
  ParticipantController.remove,
);

router.patch(
  '/:meetingId/participants/:participantId/admit',
  writeLimiter,
  validateParams(participantParamSchema),
  roleGuard,
  ParticipantController.admit,
);

// ── Self-service: participants act on their own rows ──────────────────
// Ownership is enforced inside each service via verifyParticipantOwnership.
router.patch(
  '/:meetingId/participants/:participantId/wait',
  writeLimiter,
  validateParams(participantParamSchema),
  ParticipantController.wait,
);

router.patch(
  '/:meetingId/participants/:participantId/join',
  writeLimiter,
  validateParams(participantParamSchema),
  ParticipantController.join,
);

router.patch(
  '/:meetingId/participants/:participantId/leave',
  writeLimiter,
  validateParams(participantParamSchema),
  ParticipantController.leave,
);

// ── Read – higher rate limit, host-only ──────────────────────────────
router.get(
  '/:meetingId/participants',
  readLimiter,
  validateParams(meetingParamSchema),
  roleGuard,
  ParticipantController.list,
);

module.exports = router;
