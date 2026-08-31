Two-Factor Authentication
*************************

Where a deployment enables it, an account can protect sign-in with a second
factor: an authenticator app (TOTP), backed by single-use recovery codes.
Every endpoint below acts on the authenticated caller and nobody else -- none
accepts a username, so none can be pointed at another user's second factor.

All endpoints live under ``/api/v1/totp`` and answer **404** on deployments
that have not enabled two-factor (``ENABLE_TWO_FACTOR``). On deployments where
an identity provider owns the second factor instead of Ona, the management
endpoints refuse with ``"reason": "not_managed_here"`` -- check ``status``
before offering any of these controls.

Status
------

.. raw:: html

	<pre class="prettyprint">GET /api/v1/totp/status</pre>

Reports the account's second factor and recovery-code state, and which
controls this deployment can honour.

::

    curl -X GET https://api.ona.io/api/v1/totp/status -H "Authorization: Token TOKEN_KEY"

Response::

    {
        "managedBy": "onadata",
        "capabilities": {
            "enroll": true,
            "disable": true,
            "recoveryCodes": true,
            "verify": true
        },
        "methods": [
            {"kind": "totp", "label": "default", "createdAt": "2026-08-27T09:00:00"}
        ],
        "recoveryCodes": {"generated": true, "remaining": 8}
    }

``managedBy`` is ``"idp"`` and every capability ``false`` where an identity
provider owns the factor; a client should not offer controls reported
unavailable -- the server refuses them regardless.

Enrolling an authenticator
--------------------------

Enrolment is a two-step handshake: start it to receive the secret, then
confirm it by echoing a code from the app, which proves the secret was
captured correctly. Both steps demand a signed-in session -- an API key is
refused, so a leaked key cannot change how its owner signs in.

.. raw:: html

	<pre class="prettyprint">POST /api/v1/totp/enroll/start</pre>

A first enrolment must carry the account's password. Replacing an existing
authenticator instead demands a current ``code`` (or a ``grant`` from
``verify``), the same proof disabling requires.

::

    curl -X POST https://api.ona.io/api/v1/totp/enroll/start -d "password=PASSWORD" --cookie "SSO=..."

Response (**201**)::

    {
        "qrDataUrl": "data:image/png;base64,...",
        "otpauthUri": "otpauth://totp/...",
        "secretBase32": "JBSWY3DPEHPK3PXP"
    }

One secret in three renderings: a QR image to scan, the provisioning URI, and
the base32 secret to type by hand. Starting again replaces the pending
attempt. A wrong password answers **403** with ``"reason":
"password_required"``; an account with no usable password is refused with
``"reason": "no_password_set"``. Password guesses here spend the login form's
lockout allowance -- this endpoint is not a separate brute-force budget.

.. raw:: html

	<pre class="prettyprint">POST /api/v1/totp/enroll/confirm</pre>

::

    curl -X POST https://api.ona.io/api/v1/totp/enroll/confirm -d "code=123456" --cookie "SSO=..."

Response (**200**)::

    {
        "enrolled": true,
        "codes": ["mfrggzdfmztwq2lk", "..."]
    }

Confirming activates the authenticator and returns ten fresh recovery codes.
Answers **409** when there is no pending enrolment to confirm, and **403**
when the code is wrong.

Recovery codes
--------------

Each code signs the user in once when the authenticator is lost. The set is
replaced wholesale, never appended to, so the remaining count reported by
``status`` stays honest.

.. raw:: html

	<pre class="prettyprint">POST /api/v1/totp/recovery/generate</pre>

Replaces the set and returns the new codes (**201**). The previous codes stop
working. Demands a current ``code`` or ``grant``.

.. raw:: html

	<pre class="prettyprint">POST /api/v1/totp/recovery</pre>

Returns the codes that have not been spent yet (**200**), for a user who has
lost their printout without invalidating a set that is still good. Demands a
current ``code`` or ``grant``; answers **404** when no set has been
generated. POST rather than GET so the proof travels in the body, never in a
URL or an access log.

Disabling
---------

.. raw:: html

	<pre class="prettyprint">POST /api/v1/totp/disable</pre>

::

    curl -X POST https://api.ona.io/api/v1/totp/disable -d "code=123456" -H "Authorization: Token TOKEN_KEY"

Response (**200**)::

    {"enrolled": false}

Removes every device the login view could challenge on. Demands a current
``code`` -- a recovery code counts, so a lost authenticator can still be
turned off -- or a ``grant``. Idempotent: an account with no second factor
answers the same way.

Step-up verification
--------------------

.. raw:: html

	<pre class="prettyprint">POST /api/v1/totp/verify</pre>

Checks a code without changing anything, and mints a short-lived grant for
one named operation -- for clients that verify first and act second, since a
TOTP code is spent the moment it is checked.

::

    curl -X POST https://api.ona.io/api/v1/totp/verify -d "code=123456" -d "audience=disable" -H "Authorization: Token TOKEN_KEY"

Response (**200**)::

    {"verified": true, "grant": "..."}

``audience`` names the operation the grant unlocks and must be one the
deployment recognises (``TWO_FACTOR_STEP_UP_AUDIENCES``; unknown values
answer **400**). The grant is single-use, expires after
``STEP_UP_GRANT_TTL`` seconds (default 300), and is honoured only by the
operation it was minted for. ``method`` optionally pins which factor the code
must prove -- ``totp`` or ``recovery`` -- and defaults to accepting either.

Signing in
----------

With a factor enrolled, the login page at ``/account/login/`` challenges for
a current code (or a recovery code) after the password step. Failed code
entries spend the same lockout allowance as failed passwords
(``MAX_LOGIN_ATTEMPTS`` within ``LOCKOUT_TIME``), so the second factor is not
a separate guessing budget.

Security events
---------------

Second-factor changes leave a trace. These actions are written to the
security audit log:

-  ``two-factor-enrolled`` -- an authenticator was confirmed
-  ``two-factor-disabled`` -- the second factor was removed
-  ``two-factor-verification-failed`` -- a code check failed, on any endpoint
   above or on the login page's code steps
-  ``two-factor-recovery-codes-generated`` -- the recovery set was replaced
-  ``two-factor-recovery-codes-viewed`` -- the unspent set was re-read

The account owner is emailed when an authenticator is enrolled, when
two-factor is disabled, and when the recovery set is replaced -- whoever made
the change, the owner finds out. Repeated failed code checks also alert the
owner: one email per window after ``TWO_FACTOR_FAILURE_ALERT_THRESHOLD``
failures within ``TWO_FACTOR_FAILURE_ALERT_WINDOW`` seconds (defaults 10 and
1800; a threshold of 0 disables the alert). Events are recorded, material is
not: no codes, secrets or grants appear in log entries or emails.

Deployment settings
-------------------

-  ``ENABLE_TWO_FACTOR`` -- gates every endpoint above; default ``False``
-  ``TWO_FACTOR_STEP_UP_AUDIENCES`` -- the operations ``verify`` may mint a
   grant for
-  ``STEP_UP_GRANT_TTL`` -- grant lifetime in seconds; default 300
-  ``TWO_FACTOR_FAILURE_ALERT_THRESHOLD`` / ``TWO_FACTOR_FAILURE_ALERT_WINDOW``
   -- repeated-failure alerting, described above
-  ``TWO_FACTOR_REMEMBER_COOKIE_AGE`` -- how long "don't ask again on this
   device" holds at login; unset it to challenge on every sign-in
