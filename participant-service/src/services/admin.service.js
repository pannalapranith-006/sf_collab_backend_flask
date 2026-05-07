/**
 * AdminService
 *
 * Host / co-host operations:
 *   admitGuest             – move a waiting participant into the meeting
 *   removeParticipant      – eject a participant
 *   endMeetingParticipants – bulk cleanup when a meeting ends (idempotent)
 */

const db         = require('../db');
const AppError   = require('../utils/AppError');
const AuthHelper = require('../utils/authorization');
const { ROLES, ATTENDANCE_STATUS, ERROR_MESSAGES } = require('../utils/constants');
const { validateUUID } = require('../utils/validators');
const { logFailure }   = require('./service-logger');

// FIX: Detect the DB client once at module initialisation rather than
// inside every endMeetingParticipants call.  The client type never changes
// at runtime, so re-evaluating it on every hot-path invocation is wasteful
// and makes the code harder to read.
const DB_CLIENT  = db.client?.config?.client ?? '';
const IS_PG      = ['pg', 'postgresql', 'pg-native'].includes(DB_CLIENT);

class AdminService {
  /* ------------------------------------------------------------------ */
  /*  admitGuest                                                          */
  /* ------------------------------------------------------------------ */
  /**
   * Admit a participant from the waiting room.
   * Moves attendance_status:  waiting → accepted
   * The participant must then call /join to become 'joined'.
   *
   * Idempotent for both 'accepted' AND 'joined':
   *   - 'accepted' = already admitted, not yet joined → return as-is
   *   - 'joined'   = admitted and already in the meeting → return as-is
   * Any other non-waiting status (invited, left, removed) → 409.
   */
  static async admitGuest(meetingId, participantId, admittedByUserId, requestId) {
    try {
      if (!admittedByUserId) {
        throw new AppError(ERROR_MESSAGES.UNAUTHORIZED, 401);
      }

      validateUUID(meetingId,     'Meeting ID');
      validateUUID(participantId, 'Participant ID');

      return await db.transaction(async (trx) => {
        await AuthHelper.checkMeetingState(trx, meetingId);
        await AuthHelper.verifyHostPrivileges(trx, meetingId, admittedByUserId);

        // Lock the row to prevent concurrent admit / remove races
        const current = await trx('meet_participant')
          .where({ id: participantId, meeting_id: meetingId })
          .forUpdate()
          .first();

        if (!current) {
          throw new AppError(ERROR_MESSAGES.PARTICIPANT_NOT_FOUND, 404);
        }

        // Idempotent for both 'accepted' and 'joined':
        // Both states mean admission already succeeded.
        if ([ATTENDANCE_STATUS.ACCEPTED, ATTENDANCE_STATUS.JOINED].includes(
          current.attendance_status,
        )) {
          return current;
        }

        if (current.attendance_status !== ATTENDANCE_STATUS.WAITING) {
          throw new AppError(
            `Cannot admit a participant with status '${current.attendance_status}'`,
            409,
          );
        }

        const [updated] = await trx('meet_participant')
          .where({ id: participantId })
          .update({
            attendance_status: ATTENDANCE_STATUS.ACCEPTED,
            admitted_at:       new Date(),
            admitted_by:       admittedByUserId,
          })
          .returning('*');

        return updated;
      });
    } catch (err) {
      logFailure('admitGuest_failed', { requestId, meetingId, participantId, userId: admittedByUserId }, err);
      throw err;
    }
  }

  /* ------------------------------------------------------------------ */
  /*  removeParticipant                                                   */
  /* ------------------------------------------------------------------ */
  /**
   * Eject a participant from the meeting.
   *
   * Status handling:
   *   - 'removed'  → idempotent, return as-is
   *   - 'left'     → 409: participant already left voluntarily; removing them
   *                  retroactively would corrupt the audit trail.
   *   - all others → proceed with removal
   *
   * Guards:
   *   - Cannot self-remove
   *   - Cannot remove the last host / co-host
   *   - Guests cannot hold any privileged role (DB constraint + app guard)
   */
  static async removeParticipant(meetingId, participantId, removedByUserId, requestId) {
    try {
      if (!removedByUserId) {
        throw new AppError(ERROR_MESSAGES.UNAUTHORIZED, 401);
      }

      validateUUID(meetingId,     'Meeting ID');
      validateUUID(participantId, 'Participant ID');

      return await db.transaction(async (trx) => {
        await AuthHelper.checkMeetingState(trx, meetingId);
        await AuthHelper.verifyHostPrivileges(trx, meetingId, removedByUserId);

        const current = await trx('meet_participant')
          .where({ id: participantId, meeting_id: meetingId })
          .forUpdate()
          .first();

        if (!current) {
          throw new AppError(ERROR_MESSAGES.PARTICIPANT_NOT_FOUND, 404);
        }

        // Idempotent – already removed
        if (current.attendance_status === ATTENDANCE_STATUS.REMOVED) {
          return current;
        }

        // 'left' participants must not be retroactively re-labelled 'removed'.
        // Their voluntary departure is already recorded; overwriting it corrupts
        // the audit trail and session history.
        if (current.attendance_status === ATTENDANCE_STATUS.LEFT) {
          throw new AppError(
            'Cannot remove a participant who has already left the meeting',
            409,
          );
        }

        // FIX: Belt-and-suspenders guard now covers BOTH privileged roles.
        // Previously only ROLES.HOST was checked here, leaving ROLES.CO_HOST
        // unguarded at the app layer (the DB constraint covers both, but the
        // app check should be consistent with it).
        if (
          !current.user_id &&
          [ROLES.HOST, ROLES.CO_HOST].includes(current.role_in_meeting)
        ) {
          throw new AppError(ERROR_MESSAGES.GUEST_HOST_RESTRICTION, 403);
        }

        // A host cannot remove themselves
        if (current.user_id === removedByUserId) {
          throw new AppError('Host cannot remove themselves', 403);
        }

        // Prevent removing the last host / co-host
        if ([ROLES.HOST, ROLES.CO_HOST].includes(current.role_in_meeting)) {
          const { cnt } = await trx('meet_participant')
            .where({ meeting_id: meetingId })
            .whereIn('role_in_meeting', [ROLES.HOST, ROLES.CO_HOST])
            .whereNot('id', participantId)
            .whereNotIn('attendance_status', [ATTENDANCE_STATUS.REMOVED, ATTENDANCE_STATUS.LEFT])
            .count('id as cnt')
            .first();

          if (parseInt(cnt, 10) === 0) {
            throw new AppError(ERROR_MESSAGES.LAST_HOST_REMOVAL, 403);
          }
        }

        const [updated] = await trx('meet_participant')
          .where({ id: participantId })
          .update({
            attendance_status: ATTENDANCE_STATUS.REMOVED,
            removed_at:        new Date(),
            removed_by:        removedByUserId,
          })
          .returning('*');

        return updated;
      });
    } catch (err) {
      logFailure('removeParticipant_failed', { requestId, meetingId, participantId, userId: removedByUserId }, err);
      throw err;
    }
  }

  /* ------------------------------------------------------------------ */
  /*  endMeetingParticipants                                              */
  /* ------------------------------------------------------------------ */
  /**
   * Bulk cleanup when a meeting ends.  Safe to call multiple times
   * (idempotent via ON CONFLICT DO NOTHING on participant_sessions).
   *
   * Actions:
   *   1. Write a session record for every currently-joined participant.
   *      ON CONFLICT DO NOTHING prevents duplicate rows on retry.
   *   2. Mark  joined                        → left    (with left_at)
   *   3. Mark  waiting | invited | accepted  → removed (all in one query)
   *
   * Steps 3–5 from the previous version are now ONE query (step 3 here).
   * Fewer round-trips, same result, atomically consistent.
   *
   * NOTE: duration_seconds is GENERATED ALWAYS AS — omit from INSERT.
   * NOTE: removed_by is intentionally NULL — this is a system action, not
   * a user-initiated removal, so there is no acting user to record.
   *
   * @param {string}      meetingId – UUID of the meeting that is ending
   * @param {object|null} trx       – optional existing Knex transaction
   */
  static async endMeetingParticipants(meetingId, trx = null) {
    // Validate before entering the transaction so the error surfaces cleanly
    validateUUID(meetingId, 'Meeting ID');

    const run = async (t) => {
      const meeting = await t('meetings')
        .where({ id: meetingId })
        .select('id')
        .first();

      if (!meeting) throw new AppError(ERROR_MESSAGES.MEETING_NOT_FOUND, 404);

      const nowDate = new Date();

      // ── Step 1: Write session records for all currently-joined participants ──
      // IS_PG is resolved once at module load (see top of file).
      // ON CONFLICT DO NOTHING on uq_ps_participant_joined (participant_id, joined_at)
      // makes this call fully idempotent on retry.
      // duration_seconds is a GENERATED ALWAYS column — must be omitted from INSERT.
      const insertSelectSql = `
        INSERT INTO participant_sessions
          (participant_id, meeting_id, joined_at, left_at, ended_by_meeting)
        SELECT
          id,
          meeting_id,
          joined_at,
          ?,
          ${IS_PG ? 'TRUE' : '1'}
        FROM meet_participant
        WHERE meeting_id = ?
          AND attendance_status = 'joined'
          AND joined_at IS NOT NULL
        ON CONFLICT (participant_id, joined_at) DO NOTHING
      `;

      await t.raw(insertSelectSql, [nowDate, meetingId]);

      // ── Step 2: Mark joined participants as left ──
      await t('meet_participant')
        .where({ meeting_id: meetingId, attendance_status: ATTENDANCE_STATUS.JOINED })
        .update({ attendance_status: ATTENDANCE_STATUS.LEFT, left_at: nowDate });

      // ── Step 3: Mark all remaining pre-meeting statuses as removed ──
      // FIX: Previously this was two separate UPDATE calls (waiting in one,
      // invited + accepted in another). Merged into a single whereIn query:
      //   waiting  – was in the queue when the meeting ended
      //   invited  – invite was never acted on
      //   accepted – admitted from waiting room but never clicked Join
      // All three are terminal once the meeting ends.
      // removed_by is NULL intentionally (system-initiated, no acting user).
      await t('meet_participant')
        .where({ meeting_id: meetingId })
        .whereIn('attendance_status', [
          ATTENDANCE_STATUS.WAITING,
          ATTENDANCE_STATUS.INVITED,
          ATTENDANCE_STATUS.ACCEPTED,
        ])
        .update({ attendance_status: ATTENDANCE_STATUS.REMOVED, removed_at: nowDate });
    };

    // FIX: Wrap the entire operation in try/catch so errors are logged with
    // context instead of propagating as silent unhandled rejections when
    // called from a background job or event handler.
    try {
      return trx ? await run(trx) : await db.transaction(run);
    } catch (err) {
      logFailure('endMeetingParticipants_failed', { meetingId }, err);
      throw err;
    }
  }
}

module.exports = AdminService;
