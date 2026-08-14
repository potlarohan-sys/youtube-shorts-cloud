# Free Phone-to-YouTube Cloud Workflow

This package runs the rendering and YouTube upload on a GitHub-hosted Linux runner, so the Mac may be off. A Google Form receives the phone submission, Google Drive stores the source clips, and Apps Script starts the GitHub Actions workflow.

## What the phone form collects

Create a Google Form with these exact question titles:

1. `Clip for #3` — File upload, video only, one file
2. `Clip for #2` — File upload, video only, one file
3. `#3 label` — Short answer, maximum 32 characters
4. `#2 label` — Short answer, maximum 32 characters
5. `Top 3 topic` — Short answer, such as `Funniest`
6. `YouTube channel` — Multiple choice: `GoldenBootRewind` or `Life's Highlights`
7. `Public upload approval` — Multiple choice: `NO — UPLOAD PRIVATELY` or `YES — UPLOAD PUBLICLY`

Both source clips must contain audio. The workflow stops before uploading if either clip is silent.

## One-time accounts and secrets

1. Create a GitHub repository and add this folder's contents to it.
2. In Google Cloud, enable Google Drive API and create a service account. Download its JSON key.
3. Share the Google Form's file-upload folder with the service account email as Viewer.
4. Add these GitHub Actions repository secrets:

   - `GOOGLE_SERVICE_ACCOUNT_JSON`
   - `YOUTUBE_GOLDENBOOT_TOKEN_JSON`
   - `YOUTUBE_LIFES_HIGHLIGHTS_TOKEN_JSON`

5. Link the Form to a response spreadsheet. Open **Extensions → Apps Script**, add `google-apps-script/Code.gs`, and create an installable **On form submit** trigger for `onFormSubmit`.
6. In Apps Script **Project Settings → Script Properties**, add:

   - `GITHUB_OWNER`
   - `GITHUB_REPO`
   - `GITHUB_TOKEN`

The GitHub token needs only permission to dispatch workflows for this repository. Never place token values directly in the repository or Apps Script source.

## Template rules enforced

- Two clips ordered #3 then #2
- Full-frame 9:16 crop without blurred padding or boxes
- Clean outlined ranking text
- Complete #3 label remains visible during #2
- Automatic montage-transition estimate
- Approximately four seconds of footage after the detected montage switch
- Source audio retained
- Title limited to 100 characters
- Public visibility only when the form contains the exact public-approval choice

## Free-tier expectations

GitHub Actions usage is subject to the account's included allowance. Rendering uses a standard Linux runner and normally takes several minutes. Google Drive and Apps Script quotas also apply. Failed submissions appear in the repository's **Actions** tab and never upload a partial video.
