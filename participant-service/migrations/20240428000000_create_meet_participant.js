/**
 * Migration: create_meet_participant + participant_sessions
 *
 * meet_participant     – one row per invite / seat in a meeting
 * participant_sessions – immutable audit log of each join/leave interval
 *
 * WHY A SEPARATE SESSIONS TABLE?
 *   A participant can leave and rejoin multiple times.  Storing join/leave
 *   on meet_participant would overwrite history on each cycle.
 *   participant_sessions records one row per interval so duration analytics
 *   remain accurate across reconnections.
 */

exports.up = function (knex) {
  return knex.schema.raw(`
    /* ------------------------------------------------------------------ */
    /* 1.  meet_participant                                                 */
    /* ------------------------------------------------------------------ */
    CREATE TABLE meet_participant (
      id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
      meeting_id        UUID        NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
      user_id           UUID        REFERENCES users(id) ON DELETE SET NULL,
      guest_email       VARCHAR(255),
      role_in_meeting   VARCHAR(50) NOT NULL DEFAULT 'attendee',
      attendance_status VARCHAR(30) NOT NULL DEFAULT 'invited',
      joined_at         TIMESTAMPTZ,
      left_at           TIMESTAMPTZ,
      admitted_at       TIMESTAMPTZ,
      admitted_by       UUID        REFERENCES users(id) ON DELETE SET NULL,
      invited_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      removed_at        TIMESTAMPTZ,
      removed_by        UUID        REFERENCES users(id) ON DELETE SET NULL,
      created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

      -- Exactly one of user_id or guest_email must be set
      CONSTRAINT chk_participant_identity CHECK (
        (user_id IS NOT NULL AND guest_email IS NULL) OR
        (user_id IS NULL    AND guest_email IS NOT NULL)
      ),

      -- FIX: Enforce basic email shape at the DB layer.
      -- The application layer validates properly; this is a belt-and-suspenders
      -- guard against direct DB writes or middleware bypass.
      -- Pattern: must contain exactly one @ with non-empty local and domain parts.
      CONSTRAINT chk_guest_email_format CHECK (
        guest_email IS NULL OR (
          guest_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'
          AND LENGTH(guest_email) <= 255
        )
      ),

      -- Roles must match the application enum
      CONSTRAINT chk_role_in_meeting CHECK (
        role_in_meeting IN ('host', 'co-host', 'attendee', 'panelist')
      ),

      -- Status must be one of the allowed lifecycle values
      CONSTRAINT chk_attendance_status CHECK (
        attendance_status IN ('invited','accepted','waiting','joined','left','removed')
      ),

      -- Guests cannot hold any privileged role.
      -- Mirrors the GUEST_HOST_RESTRICTION check in the application layer.
      CONSTRAINT chk_no_guest_privileged_role CHECK (
        NOT (user_id IS NULL AND role_in_meeting IN ('host', 'co-host'))
      ),

      -- left_at must be after joined_at when both are set
      CONSTRAINT chk_left_after_joined CHECK (
        left_at IS NULL OR joined_at IS NULL OR left_at >= joined_at
      )
    );

    -- One registered user per meeting
    CREATE UNIQUE INDEX uq_mp_user_per_meeting
      ON meet_participant(meeting_id, user_id)
      WHERE user_id IS NOT NULL;

    -- One guest email per meeting (case-insensitive comparison via lower())
    CREATE UNIQUE INDEX uq_mp_guest_email_per_meeting
      ON meet_participant(meeting_id, LOWER(guest_email))
      WHERE guest_email IS NOT NULL;

    -- Hot-path lookups
    CREATE INDEX idx_mp_meeting_id     ON meet_participant(meeting_id);
    CREATE INDEX idx_mp_user_id        ON meet_participant(user_id)
      WHERE user_id IS NOT NULL;
    CREATE INDEX idx_mp_status         ON meet_participant(attendance_status);
    CREATE INDEX idx_mp_meeting_status ON meet_participant(meeting_id, attendance_status);

    -- FK audit columns (for ON DELETE SET NULL reverse lookups)
    CREATE INDEX idx_mp_admitted_by ON meet_participant(admitted_by)
      WHERE admitted_by IS NOT NULL;
    CREATE INDEX idx_mp_removed_by  ON meet_participant(removed_by)
      WHERE removed_by IS NOT NULL;

    /* ------------------------------------------------------------------ */
    /* 2.  participant_sessions  (immutable join/leave intervals)           */
    /* ------------------------------------------------------------------ */
    CREATE TABLE participant_sessions (
      id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
      participant_id   UUID        NOT NULL REFERENCES meet_participant(id) ON DELETE CASCADE,
      meeting_id       UUID        NOT NULL REFERENCES meetings(id)         ON DELETE CASCADE,
      joined_at        TIMESTAMPTZ NOT NULL,

      -- FIX: left_at must be NOT NULL on session rows.
      -- participant_sessions is only ever written when a session ends (leave /
      -- endMeetingParticipants), so left_at is always known at insert time.
      -- Allowing NULL would make duration_seconds always NULL for those rows,
      -- silently breaking analytics queries.
      left_at          TIMESTAMPTZ NOT NULL,

      -- Computed automatically by the DB from joined_at / left_at.
      -- GREATEST(0, …) guards against negative values from clock skew.
      duration_seconds INTEGER     GENERATED ALWAYS AS (
                         GREATEST(0, EXTRACT(EPOCH FROM left_at - joined_at)::integer)
                       ) STORED,

      ended_by_meeting BOOLEAN     NOT NULL DEFAULT FALSE,
      created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

      -- FIX: Enforce temporal integrity — a session cannot end before it starts.
      CONSTRAINT chk_ps_left_after_joined CHECK (left_at >= joined_at)
    );

    -- Primary deduplication key: one session per participant per join event
    CREATE UNIQUE INDEX uq_ps_participant_joined
      ON participant_sessions(participant_id, joined_at);

    CREATE INDEX idx_ps_participant_id ON participant_sessions(participant_id);
    CREATE INDEX idx_ps_meeting_id     ON participant_sessions(meeting_id);

    /* ------------------------------------------------------------------ */
    /* 3.  invite_outbox  (pending guest invite emails)                     */
    /* ------------------------------------------------------------------ */
    -- FIX: invite_outbox was referenced in invite.service.js (guest invite
    -- email queueing) but was never created here.  Without this table every
    -- guest invitation would fail with an undefined-relation DB error.
    CREATE TABLE invite_outbox (
      id             UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
      participant_id UUID         NOT NULL UNIQUE REFERENCES meet_participant(id) ON DELETE CASCADE,
      meeting_id     UUID         NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
      email          VARCHAR(255) NOT NULL,
      created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
    );

    CREATE INDEX idx_io_meeting_id ON invite_outbox(meeting_id);
  `);
};

exports.down = function (knex) {
  // Drop in reverse dependency order
  return knex.schema.raw(`
    DROP TABLE IF EXISTS invite_outbox         CASCADE;
    DROP TABLE IF EXISTS participant_sessions  CASCADE;
    DROP TABLE IF EXISTS meet_participant      CASCADE;
  `);
};
