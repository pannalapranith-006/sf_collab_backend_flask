/**
 * ParticipantController
 *
 * Thin HTTP adapter layer.  Each method:
 *   1. Extracts validated inputs from req
 *   2. Delegates to the appropriate service
 *   3. Serialises the result into a uniform JSON envelope
 *
 * Error handling is delegated entirely to the Express error middleware
 * via next(error).  No error is swallowed or re-wrapped here.
 */

const InviteService  = require('../services/invite.service');
const JoinService    = require('../services/join.service');
const LeaveService   = require('../services/leave.service');
const AdminService   = require('../services/admin.service');
const { HTTP_STATUS } = require('../utils/constants');

// FIX: ParticipantQueryService is required by the list action but was
// not present in the codebase, causing a MODULE_NOT_FOUND crash on
// startup.  Guard the require so the rest of the controller is usable
// while the service is being implemented, and fail fast only on the
// specific route that needs it.
let ParticipantQueryService;
try {
  ParticipantQueryService = require('../services/participant-query.service');
} catch {
  ParticipantQueryService = null;
}

/**
 * Extract the acting user's ID from req.user.
 *
 * Guests (req.user.isGuest === true) do not have a user_id in the
 * registered-user sense; return null so services can enforce
 * appropriate restrictions.
 *
 * @param {object} reqUser – req.user set by authGuard
 * @returns {string|null}
 */
function resolveUserId(reqUser) {
  return reqUser?.isGuest ? null : (reqUser?.id ?? null);
}

class ParticipantController {
  /* ------------------------------------------------------------------ */
  /*  POST /:meetingId/participants/invite                                */
  /* ------------------------------------------------------------------ */
  static async invite(req, res, next) {
    try {
      const participant = await InviteService.invite(
        req.params.meetingId,
        req.body,
        resolveUserId(req.user),
        req.id,
      );
      res.status(HTTP_STATUS.CREATED).json({
        success: true,
        data:    participant,
        message: 'Participant invited successfully',
      });
    } catch (err) {
      next(err);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  DELETE /:meetingId/participants/:participantId                      */
  /* ------------------------------------------------------------------ */
  static async remove(req, res, next) {
    try {
      await AdminService.removeParticipant(
        req.params.meetingId,
        req.params.participantId,
        resolveUserId(req.user),
        req.id,
      );
      // 204 No Content – intentionally no body
      res.status(HTTP_STATUS.NO_CONTENT).send();
    } catch (err) {
      next(err);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  PATCH /:meetingId/participants/:participantId/admit                 */
  /* ------------------------------------------------------------------ */
  static async admit(req, res, next) {
    try {
      const participant = await AdminService.admitGuest(
        req.params.meetingId,
        req.params.participantId,
        resolveUserId(req.user),
        req.id,
      );
      res.status(HTTP_STATUS.OK).json({
        success: true,
        data:    participant,
        message: 'Participant admitted successfully',
      });
    } catch (err) {
      next(err);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  PATCH /:meetingId/participants/:participantId/join                  */
  /* ------------------------------------------------------------------ */
  static async join(req, res, next) {
    try {
      const participant = await JoinService.trackJoin(
        req.params.meetingId,
        req.params.participantId,
        req.user,
        req.id,
      );
      res.status(HTTP_STATUS.OK).json({
        success: true,
        data:    participant,
        message: 'Participant joined successfully',
      });
    } catch (err) {
      next(err);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  PATCH /:meetingId/participants/:participantId/leave                 */
  /* ------------------------------------------------------------------ */
  static async leave(req, res, next) {
    try {
      const participant = await LeaveService.trackLeave(
        req.params.meetingId,
        req.params.participantId,
        req.user,
        req.id,
      );
      res.status(HTTP_STATUS.OK).json({
        success: true,
        data:    participant,
        message: 'Participant left successfully',
      });
    } catch (err) {
      next(err);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  PATCH /:meetingId/participants/:participantId/wait                  */
  /* ------------------------------------------------------------------ */
  static async wait(req, res, next) {
    try {
      const participant = await JoinService.setWaiting(
        req.params.meetingId,
        req.params.participantId,
        req.user,
        req.id,
      );
      res.status(HTTP_STATUS.OK).json({
        success: true,
        data:    participant,
        message: 'Participant moved to waiting room',
      });
    } catch (err) {
      next(err);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  GET /:meetingId/participants                                        */
  /* ------------------------------------------------------------------ */
  static async list(req, res, next) {
    try {
      // FIX: Fail with a clear 501 if ParticipantQueryService hasn't been
      // implemented yet, rather than crashing the process on startup with
      // MODULE_NOT_FOUND or calling undefined at runtime.
      if (!ParticipantQueryService) {
        return res.status(501).json({
          success: false,
          message: 'Participant list endpoint is not yet implemented',
        });
      }

      const result = await ParticipantQueryService.listParticipants(
        req.params.meetingId,
        req.query,
        resolveUserId(req.user),
        req.id,
      );

      res.status(HTTP_STATUS.OK).json({
        success: true,
        data:    result.data,
        meta:    { total: result.total },
        message: 'Participants fetched successfully',
      });
    } catch (err) {
      next(err);
    }
  }
}

module.exports = { ParticipantController };
