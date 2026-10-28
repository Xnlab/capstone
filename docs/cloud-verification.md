# Cloud verification — 2026-10-29 (Asia/Seoul)

- Public URL: https://capstone-cloud.vercel.app
- Verified deployment: `dpl_J4r3PLU7oruGZxY3JHTMVYNvSsZg`, Production, READY.
- Remote Next.js and FastAPI builds completed successfully.
- Local server test suite: 30 tests passed.
- Public API smoke tests passed: registration/login, unauthenticated rejection,
  cross-account contract/document/template isolation, all nine built-in native
  formats and PDFs, and rasterized full-page previews.
- DOCX, HWPX and positioned PDF original upload, durable retrieval and automatic
  filling passed. Uploaded HWPX retained an original image/package entry.
- HWP rejection and uploaded HWPX PDF-preview limitation returned expected errors.
- Browser: registration reached the company screen; library displayed nine cards;
  the commencement form opened a complete, readable A4 page. Logged out afterward.
- Supabase security advisor returned no lints. This does not replace an application
  penetration test, legal review, or production security audit.
- Seven disposable fictional accounts and their associated contracts, documents,
  files and audit entries were removed after testing. No real user data was touched.
- Original checkout still has only its pre-existing `web/package-lock.json` change.
- No paid plan, AI provider, SMTP provider, domain purchase, or paid add-on enabled.

The app uses Vercel Services Beta and Supabase Free. Hosting quotas or provider
inactivity policies can still limit availability. User accounts are independent;
shared-contract collaborative editing is not implemented.
