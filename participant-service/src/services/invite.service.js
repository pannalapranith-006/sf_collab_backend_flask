/**
 * InviteService
 *
 * Handles inviting registered users and external guests to a meeting.
 *
 * Input validation responsibilities:
 *   - Email FORMAT is validated here (service layer) as a defence-in-depth
 *     guard even though the route validator schema also checks it.
 *   - role_in_meeting must be a recognised enum value (checked here).
 *   - UUID format for meetingId / user_id is validated here.
 *
 * Business rule enforcement (host privileges, duplicate prevention,
 * guest-host restriction) and atomic persistence also happen here.
 */

const db               = require('../db');
const ParticipantModel = require('../models/participant.model');
const AppError         = require('../utils/AppError');
const AuthHelper       = require('../utils/authorization');
const { ROLES, ATTENDANCE_STATUS, ERROR_MESSAGES } = require('../utils/constants');
const { validateUUID } = require('../utils/validators');
const { logFailure }   = require('./service-logger');

// RFC-5321-inspired basic email regex.
// Full RFC compliance requires a parser; this regex catches the common
// invalid formats (missing @, missing domain, whitespace) without false
// positives on valid addresses.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

class InviteService {
  /**
   * Invite a participant (registered user or guest) to a meeting.
   *
   * @param {string}  meetingId       – UUID of the target meeting
   * @param {object}  data            – { user_id?, guest_email?, role_in_meeting? }
   * @param {string}  invitedByUserId – UUID of the acting host/co-host
   * @param {string}  requestId       – correlation ID for logging
   * @returns {object} Newly created meet_participant row
   */
  static async invite(meetingId, data, invitedByUserId, requestId) {
    try {
      // Auth check first — return 401 before leaking any input-validation detail
      if (!invitedByUserId) {
        throw new AppError(ERROR_MESSAGES.UNAUTHORIZED, 401);
      }

      validateUUID(meetingId, 'Meeting ID');

      const email = data.guest_email
        ? data.guest_email.toLowerCase().trim()
        : null;

      // FIX: Validate email format inside the service as a defence-in-depth
      // guard. If the route validator middleware is bypassed (direct test call,
      // misconfigured schema, future route refactor) an invalid address would
      // otherwise be persisted silently and fail the DB CHECK constraint with
      // an opaque 500 instead of a clear 400.
      if (email && !EMAIL_RE.test(email)) {
        throw new AppError('Invalid guest email address format', 400);
      }

      // Default to 'attendee' — ROLES.ATTENDEE maps to the DB CHECK value 'attendee'
      const role = data.role_in_meeting ?? ROLES.ATTENDEE;

      // Guests cannot hold a privileged role (belt-and-suspenders;
      // DB constraint chk_no_guest_privileged_role enforces the same rule)
      if ([ROLES.HOST, ROLES.CO_HOST].includes(role) && !data.user_id) {
        throw new AppError(ERROR_MESSAGES.GUEST_HOST_RESTRICTION, 403);
      }

      if (data.user_id) {
        validateUUID(data.user_id, 'User ID');
      } else if (!email) {
        throw new AppError('Must provide either user_id or guest_email', 400);
      }

      return await db.transaction(async (trx) => {
        // Verify the meeting is in a state that accepts new invites
        await AuthHelper.checkMeetingState(trx, meetingId);

        // Only hosts / co-hosts may invite
        await AuthHelper.verifyHostPrivileges(trx, meetingId, invitedByUserId);

        // Reject if the same user / guest is already invited
        await AuthHelper.checkDuplicateInvite(trx, meetingId, data);

        // Ensure the target user account actually exists
        if (data.user_id) {
          const user = await trx('users').where({ id: data.user_id }).first();
          if (!user) throw new AppError('User not found', 404);
        }

        const participant = await ParticipantModel.create(
          {
            meeting_id:        meetingId,
            user_id:           data.user_id ?? null,
            guest_email:       email,
            role_in_meeting:   role,
            attendance_status: ATTENDANCE_STATUS.INVITED,
            invited_at:        new Date(),
          },
          trx,
        );

        // Queue an outbound invite email for guests (idempotent upsert)
        if (email) {
          await trx('invite_outbox')
            .insert({
              participant_id: participant.id,
              meeting_id:     meetingId,
              email,
            })
            .onConflict('participant_id')
            .ignore();
        }

        return participant;
      });
    } catch (err) {
      logFailure('inviteParticipant_failed', { requestId, meetingId, userId: invitedByUserId }, err);
      throw err;
    }
  }
}

module.exports = InviteService;
