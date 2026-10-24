# Free public deployment with Render

This project is ready to run as a free Render web service. The deployed app gets
a public HTTPS address that works from phones and computers on any network. The
laptop that created it does not need to remain switched on.

## Before uploading

- Upload the `ai_exzam_mvp` folder to a private GitHub repository.
- Do not upload `.env`. The included `.gitignore` excludes it automatically.
- Never paste the Groq API key into source files or GitHub.

## Deploy

1. Sign in to Render and select **New > Blueprint**.
2. Connect the GitHub repository containing this folder.
3. Render reads `render.yaml`. Choose the **Free** plan if asked.
4. When prompted for `GROQ_API_KEY`, paste the key into Render's secret field.
5. Create the Blueprint and wait for the deployment to finish.
6. Open the generated `https://...onrender.com` address and share that address.

## Free-tier behavior

- The service sleeps after a period without visitors. The first visit after
  sleeping can take roughly a minute to open.
- Student files are stored on temporary free-server storage. They can disappear
  after a restart or redeployment. This is suitable for a POC, not permanent
  school records.
- Every visitor uses the app owner's Groq API key and its usage limits. Never
  display that key in the browser or send it to students.

For permanent student history, add authentication and a hosted database before
using the app beyond a small controlled trial.
