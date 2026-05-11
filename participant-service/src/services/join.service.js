/**
 * JoinService
 *
 * Handles participant entry into an active meeting.
 *
 * Status lifecycle handled here:
 *
 *   invited  ──────────────────────────────► joined   (direct join, no waiting room)
 *   accepted (post-admit from waiting room) ─► joined
 *   invited  ──────────────────────────────► waiting  (waiting-room flow start)
 *
 * Blocked transitions (enforced explicitly with 409):
 *   accepted → waiting  (admission must not be silently undone)
 *   joined   → waiting  (participant is already in the meeting)
 *   left     → waiting  (participant has already departed)
 *   removed  → waiting  (participant has been ejected)
 */

const db         = require('../db');
const AppError   = require('../utils/AppError');
const AuthHelper = require('../utils/authorization');
const { ATTENDANCE_STATUS, ERROR_MESSAGES } = require('../utils/constants');
const { validateUUID } = require('../utils/validators');
const { logFailure }   = require('./service-logger');

class JoinService {
  /* ------------------------------------------------------------------ */
  /*  trackJoin                                                           */
  /* ------------------------------------------------------------------ */
  /**
   * Mark a participant as 'joined' and record the join timestamp.
   *
   * Allowed prior states: 'invited', 'accepted'
   * Idempotent: already-joined rows are returned unchanged.
   *
   * @param {string} meetingId     – UUID of the meeting
   * @param {string} participantId – UUID of the meet_participant row
   * @param {object} caller        – { id, guestParticipantId? } from auth middleware
   * @param {string} requestId     – correlation ID for logging
   */
  static async trackJoin(meetingId, participantId, caller, requestId) {
    try {
      // FIX: Auth check moved before UUID validation.
      // An unauthenticated caller should receive 401, not a 400/422 from UUID
      // validation that leaks information about the parameter structure.
      if (!caller) throw new AppError(ERROR_MESSAGES.UNAUTHORIZED, 401);

      validateUUID(meetingId,     'Meeting ID');
      validateUUID(participantId, 'Participant ID');

      return await db.transaction(async (trx) => {
        await AuthHelper.checkMeetingState(trx, meetingId, /* requireActive */ false);

        const current = await trx('meet_participant')
          .where({ id: participantId, meeting_id: meetingId })
          .forUpdate()
          .first();

        if (!current) throw new AppError(ERROR_MESSAGES.PARTICIPANT_NOT_FOUND, 404);

        await AuthHelper.verifyParticipantOwnership(current, caller);

        // Idempotent
        if (current.attendance_status === ATTENDANCE_STATUS.JOINED) return current;

        // 'waiting' participants must be admitted first (status → 'accepted')
        // Any other status (removed, left) produces a clear 409.
        const [updated] = await trx('meet_participant')
          .where({ id: participantId })
          .whereIn('attendance_status', [
            ATTENDANCE_STATUS.INVITED,
            ATTENDANCE_STATUS.ACCEPTED,
          ])
          .update({
            attendance_status: ATTENDANCE_STATUS.JOINED,
            joined_at:         new Date(),
          })
          .returning('*');

        if (!updated) {
          throw new AppError(
            `Cannot join from status '${current.attendance_status}'`,
            409,
          );
        }

        return updated;
      });
    } catch (err) {
      logFailure('trackJoin_failed', { requestId, meetingId, participantId, userId: caller?.id }, err);
      throw err;
    }
  }

  /* ------------------------------------------------------------------ */
  /*  setWaiting                                                          */
  /* ------------------------------------------------------------------ */
  /**
   * Move a participant into the waiting room.
   *
   * Allowed prior state: 'invited' ONLY.
   *
   * 'accepted' → 'waiting' is intentionally blocked: once a host has
   * admitted a participant they must not silently fall back into the queue.
   * The host must remove and re-invite if they want to revoke admission.
   *
   * @param {string} meetingId     – UUID of the meeting
   * @param {string} participantId – UUID of the meet_participant row
   * @param {object} caller        – from auth middleware
   * @param {string} requestId     – correlation ID for logging
   */
  static async setWaiting(meetingId, participantId, caller, requestId) {
    try {
      // FIX: Auth check moved before UUID validation (same reason as trackJoin)
      if (!caller) throw new AppError(ERROR_MESSAGES.UNAUTHORIZED, 401);

      validateUUID(meetingId,     'Meeting ID');
      validateUUID(participantId, 'Participant ID');

      return await db.transaction(async (trx) => {
        const meeting = await AuthHelper.checkMeetingState(trx, meetingId);

        if (!meeting.waiting_room_enabled) {
          throw new AppError('This meeting does not have a waiting room enabled', 409);
        }

        const current = await trx('meet_participant')
          .where({ id: participantId, meeting_id: meetingId })
          .forUpdate()
          .first();

        if (!current) throw new AppError(ERROR_MESSAGES.PARTICIPANT_NOT_FOUND, 404);

        await AuthHelper.verifyParticipantOwnership(current, caller);

        // Idempotent
        if (current.attendance_status === ATTENDANCE_STATUS.WAITING) return current;

        // Only 'invited' may enter the waiting room.
        // 'accepted' participants have already been let in by the host.
        if (current.attendance_status !== ATTENDANCE_STATUS.INVITED) {
          throw new AppError(
            `Cannot move to waiting room from status '${current.attendance_status}'`,
            409,
          );
        }

        const [updated] = await trx('meet_participant')
          .where({ id: participantId })
          .update({ attendance_status: ATTENDANCE_STATUS.WAITING })
          .returning('*');

        return updated;
      });
    } catch (err) {
      logFailure('setWaiting_failed', { requestId, meetingId, participantId, userId: caller?.id }, err);
      throw err;
    }
  }
}

module.exports = JoinService;
