# Security rollout — 2026-10-29

## Implemented, not yet applied to the live cloud

- Opaque random sessions stored only as SHA-256 hashes server-side. Browser authentication uses an HttpOnly, SameSite=Strict cookie (Secure + __Host- prefix in cloud). Legacy JWT/bearer login is rejected. Session lifetime is at most 8 hours.
- Every authenticated write requires a session-bound CSRF header. Login/register reject foreign Origin and cross-site browser requests. Browser fetches include credentials; no session token is returned in JSON or kept in localStorage.
- Logout revokes the server session. All-device logout revokes every session and related sensitive grants for that account.
- Shared DB rate counters limit sign-in, registration and sensitive reauthentication attempts per account and source address. Address/account keys are HMACs, not plaintext identifiers. Only trusted deployment proxy handling should determine the client address; add provider firewall limits as a second layer.
- Sensitive operations require password reauthentication and a 2-minute, single-use, session- and resource-bound grant. Stamp read, replacement/removal, built-in stamped downloads, ZIP and email routes are covered. Normal previews and AI projection do not render registered stamps. A stamp embedded in an uploaded original cannot be removed by this mechanism.
- General company responses report has_seal, never the image. Separate approved endpoint reveals it. Downloads and sensitive uses leave minimal audit entries.
- Library administrators are explicit reviewed user IDs in library_admins. LIBRARY_ADMIN_EMAILS no longer grants a role at request time. During a paused cutover, --preserve-existing-admins can snapshot already-reviewed existing assignments; review those accounts before using it. New admin grants require a reviewed database migration.
- Other-account ownership checks cover document and contract actions; the regression suite also checks private template access by a library administrator. DB backend policy is still backend-wide: per-tenant DB RLS is not claimed.
- Authenticated encryption (Fernet/MultiFernet) protects new writes of company text including bank/contact fields and seal; contract title/client/description; document title/values; template name/description/aliases/metadata/mapping; original DB files; and audit detail. IDs, account login identity, contract numeric amounts/dates, categories/status and timestamps remain queryable metadata. Server memory, exported files and provider backups have separate exposure.
- Local original files are encrypted after analysis; decrypted request files are deleted after response, with hourly/daily cleanup of abandoned temp files. External scripts using resolve() must unlink returned temporary paths themselves.
- Expired originals are inaccessible immediately, deleted hourly in a persistent local server and daily in Vercel (03:00 UTC, around noon KST). Authenticated scheduled endpoint fails closed without CRON_SECRET. This expires originals, not all contracts/document values.
- A reauthenticated privacy action deletes own contracts/documents/private templates/company/stamp, retains account, public forms and minimal security logs. Exported/emailed copies and backups are not represented as immediately erased.

## Cloud rollout order

1. Verify the target is capstone-cloud only. Pause writes and create/verify a Supabase backup before migration. No provider configuration, live schema, production key or deployment was changed by the local implementation.
2. Generate a fresh Fernet key and store it as DATA_ENCRYPTION_KEYS in the Vercel project secret environment. Never reuse SECRET_KEY or put encryption keys in the DB, Git, deployment manifests or console output. Keep an independent protected backup of the key.
3. Generate CRON_SECRET (at least 32 random characters) and validate SECRET_KEY is a strong unique secret. Configure CORS_ORIGINS to actual allowed origins. Frontend/API must share a site; production same-origin /api/v1 is recommended.
4. Generate additive cloud schema SQL: from server run DATABASE_SCHEMA=capstone with python scripts/migrate_security.py --schema-sql. Apply it as the schema administrator, not by granting the application new DDL permissions. Preserve existing RLS/private schema settings.
5. Deploy the new frontend and API together. Do not return to the old reader after encrypted data has been written. Existing JWT users must sign in again. Confirm HttpOnly/Secure/SameSite and CSRF rejection on the production hostname.
6. Run python scripts/migrate_security.py --apply --backup-confirmed against the exact cloud DB using the same encryption key, while writes remain paused. It rewrites legacy values without printing contents. Repeat is supported with all old keys still available. Verify retrieval/output and raw stored values before reopening writes.
7. Verify server-side logout, all-device logout, other-account denied responses, stamp grants (wrong scope/session/replay/expiry), unapproved previews, cron authorization and daily scheduling. Do not use real seals/documents for smoke tests.

## Local migration

By default the local encryption key is generated once in ignored server/storage/.data-encryption.key. Never delete or regenerate this file for an existing database. Local file ACLs inherit the workspace's protection; protect the workstation/account and encrypted backups separately. Prefer externally managed DATA_ENCRYPTION_KEYS for shared or production installations.

The application reads legacy plaintext to permit controlled migration. A source update alone does not retroactively encrypt all existing rows. Run the migration only after backing up the local DB/originals and pausing the old server. The migration does not migrate cloud DBs implicitly.

## Key rotation and limits

DATA_ENCRYPTION_KEYS accepts newest-first comma-separated keys. Reads try every retained key; new writes use the first. Re-run the data migration to rewrite rows. Local encrypted originals require a separate validated re-encryption/rotation operation (the migration verifies but does not rotate already encrypted files). Retain old keys until legacy files and required backups have expired. Key loss makes encrypted data unrecoverable.

This is not zero-knowledge or end-to-end encryption: the application server can decrypt authorized data. MFA, user-scoped DB RLS, managed KMS, application penetration testing, alerting/provider monitoring and verified provider backup-erasure timelines remain follow-up work. Functional tests do not certify production security.

## Verification in this workspace

- Final isolated regression suite: 46 tests passed, including cookie flags, CSRF/origin rejection, server-side/all-device logout, expiry, shared login throttling, single-use scoped grants, unstamped previews, denied other-account routes, explicit admin IDs, ownerless-private templates, authenticated encryption/tamper rejection, repeatable legacy migration and reauthenticated own-data deletion.
- Frontend lint: no errors, one pre-existing navigation warning in the API client. TypeScript check and Next.js Webpack production build passed. The default local Turbopack build failed when its CSS child process exited before connecting; Webpack was used to validate this change. No claim of a production build/deploy is made here.
- The existing local SQLite database and 3 originals were backed up to an authenticated encrypted archive under ignored server/storage/security-backups. Backup decryption was checked before migration. Local migration completed; all document values and original bytes were compared against the backup, and sample PDF rendering was verified. Existing reviewed local admin assignments were snapshotted once to explicit user IDs. The local encryption key must be retained separately from the database and backup.
- Cloud rollout was not executed. Vercel rejected access to the documented deployment team (403); the connected account lists a different team. Team authorization could not be generated for the deployment team (404). Supabase tool access was not available. Do not interpret locally passing tests as changes to the production service.
