/**
 * LeaveService
 *
 * Tracks a participant voluntarily leaving a meeting.
 *
 * On a successful leave:
 *   1. meet_participant.attendance_status → 'left', left_at set
 *   2. An immutable row is inserted into participant_sessions
 *
 * The session insert uses ON CONFLICT DO NOTHING so that retried
 * requests never produce duplicate session rows or crash with a
 * unique-violation error.
 *
 * duration_seconds is omitted from INSERT because it is a
 * GENERATED ALWAYS AS column; the DB computes it from joined_at / left_at.
 */

const db         = require('../db');
const AppError   = require('../utils/AppError');
const AuthHelper = require('../utils/authorization');
const { ATTENDANCE_STATUS, ERROR_MESSAGES } = require('../utils/constants');
const { validateUUID } = require('../utils/validators');
const { logFailure }   = require('./service-logger');

class LeaveService {
  /* ------------------------------------------------------------------ */
  /*  trackLeave                                                          */
  /* ------------------------------------------------------------------ */
  /**
   * Mark a participant as 'left' and write a session audit record.
   *
   * Idempotent: if the participant has already left, the existing row
   * is returned without modifying the database.
   *
   * Only a 'joined' participant can leave.  Any other status
   * (invited, waiting, accepted, removed) results in 409.
   *
   * @param {string} meetingId     – UUID of the meeting
   * @param {string} participantId – UUID of the meet_participant row
   * @param {object} caller        – { id, guestParticipantId? } from auth middleware
   * @param {string} requestId     – correlation ID for logging
   * @returns {object} Updated participant row with duration_seconds appended
   */
  static async trackLeave(meetingId, participantId, caller, requestId) {
    try {
      // FIX: Auth check moved before UUID validation.
      // An unauthenticated caller should receive 401, not 400/422 from UUID
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

        // Idempotent: already left
        if (current.attendance_status === ATTENDANCE_STATUS.LEFT) {
          return LeaveService.formatLeaveResponse(current);
        }

        if (current.attendance_status !== ATTENDANCE_STATUS.JOINED) {
          throw new AppError(
            `Cannot leave from status '${current.attendance_status}'`,
            409,
          );
        }

        const leftAt = new Date();

        // Atomic: both the status update and the session insert happen inside
        // the same transaction — either both persist or neither does.
        const [updated] = await trx('meet_participant')
          .where({ id: participantId, attendance_status: ATTENDANCE_STATUS.JOINED })
          .update({
            attendance_status: ATTENDANCE_STATUS.LEFT,
            left_at:           leftAt,
          })
          .returning('*');

        if (!updated) {
          // A concurrent leave request won the race.  Re-fetch the current
          // row to build an accurate response.
          const refetch = await trx('meet_participant')
            .where({ id: participantId })
            .first();

          // Guard: the row could theoretically be deleted (e.g. meeting hard-
          // deleted via CASCADE) between the forUpdate lock and the re-fetch.
          if (!refetch) {
            throw new AppError(ERROR_MESSAGES.PARTICIPANT_NOT_FOUND, 404);
          }

          return LeaveService.formatLeaveResponse(refetch);
        }

        // ON CONFLICT DO NOTHING makes this idempotent on retry.
        // duration_seconds is a GENERATED ALWAYS column — omit from INSERT.
        // FIX: Guard against a NULL joined_at before inserting into
        // participant_sessions, whose joined_at column is NOT NULL.
        // trackJoin always sets joined_at when transitioning to 'joined',
        // so this should never be null in practice, but an explicit guard
        // prevents a silent DB NOT NULL violation if data is ever inconsistent.
        if (!updated.joined_at) {
          throw new AppError(
            'Cannot record session: participant joined_at timestamp is missing',
            500,
          );
        }

        await trx('participant_sessions')
          .insert({
            participant_id:   updated.id,
            meeting_id:       updated.meeting_id,
            joined_at:        updated.joined_at,
            left_at:          updated.left_at,
            ended_by_meeting: false,
          })
          .onConflict(['participant_id', 'joined_at'])
          .ignore();

        return LeaveService.formatLeaveResponse(updated);
      });
    } catch (err) {
      logFailure('trackLeave_failed', { requestId, meetingId, participantId, userId: caller?.id }, err);
      throw err;
    }
  }

  /* ------------------------------------------------------------------ */
  /*  formatLeaveResponse                                                 */
  /* ------------------------------------------------------------------ */
  /**
   * Append a computed duration_seconds to the participant row so clients
   * receive the value without an extra round-trip.
   * This mirrors the GENERATED ALWAYS AS column in participant_sessions.
   *
   * @param  {object} row – meet_participant row
   * @returns {object}
   */
  static formatLeaveResponse(row) {
    const durationMs =
      row.joined_at && row.left_at
        ? new Date(row.left_at).getTime() - new Date(row.joined_at).getTime()
        : 0;

    return {
      ...row,
      duration_seconds: Math.floor(Math.max(0, durationMs) / 1000),
    };
  }
}

module.exports = LeaveService;
