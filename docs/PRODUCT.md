# JobScout AI — product scope

## Core user journey

1. Create an account.
2. Choose English or Russian.
3. Upload a PDF/DOCX resume.
4. Review the extracted candidate profile.
5. Set target roles, skills, regions, remote preference, salary floor and exclusions.
6. JobScout periodically collects remote jobs from allowed public sources.
7. The matching engine ranks each role against that specific user.
8. The user sees matching skills, gaps and a fit score.
9. The user can save a role, prepare an application pack and mark application progress.
10. The tracker keeps Saved → Applied → Interview → Offer / Rejected state.

## Mobile / iPhone

The React client is responsive and configured as a PWA. After deployment over HTTPS, iPhone users can install it from Safari using Share → Add to Home Screen. The app then launches in standalone mode.

The repo also includes Capacitor configuration so the same web client can later be wrapped as a native iOS application. App Store distribution requires Apple Developer signing and an Xcode build on macOS.

## Enabled public job sources

- Remote OK
- We Work Remotely
- Himalayas
- Jobicy

Each source is shown in the UI and original listing/application links are preserved.

## Deliberately not enabled by default

Sources whose public feed terms are not suitable for a signup-based multi-user job product are not used without an appropriate commercial/private agreement.
