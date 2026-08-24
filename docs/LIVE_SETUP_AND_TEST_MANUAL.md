# Cordia live setup and test manual

This manual is for an approved test account. Do not use a customer account, paste credentials into notes, or copy Cordia's model output into an evidence report.

Current result: **Not verified with OpenAI.** The verification environment did not have an approved server-side OpenAI credential, so no model call was made.

## What each evidence label means

| Label | Meaning |
|---|---|
| Simulated | A test double exercised the contract. No real provider was contacted. |
| Configured | The server reports that required configuration is present. This does not prove that it works. |
| Verified locally | An approved real provider was observed through the authenticated application route in a controlled local environment. |
| Verified live | The same approved observation was completed against the released service. |
| Not verified | No qualifying real-provider observation exists. Do not describe this state as working live. |

## Before the test

1. Ask the service operator to confirm that the test environment is approved for a real-provider check and that its status is **Configured**. Do not ask for or handle the credential yourself.
2. Use a dedicated test account whose free-turn allowance may be consumed.
3. Keep the evidence note blank except for the approved bounded fields: commit, UTC time, model identifier, HTTP status, accepted envelope kind, workspace revision, and remaining allowance.
4. If the operator cannot confirm both server configuration and an authenticated test account, stop and label the result **Not verified**.

## Sign in

1. Open the Cordia sign-in page.
2. Enter the approved test account address and password, then choose **Sign in**.
3. If Cordia requests a verification code, retrieve it through the account's normal email flow and enter it on the page. Never paste it into a report or chat.
4. Confirm that Cordia opens the existing workspace. If the account has no workspace, Cordia will open Surveyor instead.

## Complete Surveyor and confirm memory

1. Choose **Talk to Surveyor** and answer the displayed questions using non-sensitive test information.
2. Continue until Surveyor reports that it has enough context.
3. Open **Profile** and review the **Operator profile** summary. Confirm that it reflects the test answers and is described as an inspectable working picture, not a score.
4. Choose **Build my workspace** when it appears. Wait for Cordia to open the new workspace.
5. Confirm that the workspace greeting or summary reflects the compiled test profile. Do not copy raw survey answers into the verification note.

## Send and reload one workspace message

1. In the Cordia Agent panel, type one short, non-sensitive test message.
2. Choose **Send** once. Do not click again while the request is in progress.
3. Confirm that the page shows one Cordia turn and, when applicable, one pending proposal. A proposal is not a connected or executed integration.
4. Record only the bounded observation fields listed under **Before the test**. Do not record the message text or Cordia's output.
5. Reload the page.
6. Confirm that the same turn is still present and that the workspace revision did not move again merely because of the reload.
7. Use the application's unchanged-draft retry once only when intentionally testing duplicate replay. Confirm that the visible turn and remaining allowance do not increase a second time.

## Check the free-turn limit

1. Use only the approved disposable test account for this check.
2. Complete successful Cordia turns one at a time and note the bounded remaining allowance after each accepted turn.
3. Confirm that failed, rejected, conflicting, and duplicate-replay requests do not consume a turn.
4. After ten successful turns, submit one more ordinary test message.
5. Confirm that Cordia preserves the workspace and draft and displays: **Free agent actions used. Upgrade to continue.**
6. Confirm that the extra request did not produce a model call, a new turn, or another revision.

## Recover from common failures

- **Signed out:** return to the sign-in page, sign in again, reopen the saved workspace, and check whether the prior turn is already present before retrying.
- **Cordia is not configured:** stop. Ask the service operator to restore approved server-side configuration; do not supply a credential through the browser or chat.
- **Cordia could not complete the request:** keep the unchanged draft, wait briefly, and choose **Send** once. Cordia should reuse the retry identity for the unchanged message.
- **Workspace refreshed because of a conflict:** wait for the refresh to finish, confirm the newest workspace state, then retry once.
- **Workspace does not refresh:** reload the page and confirm the saved turn and revision before sending anything again.
- **Usage limit shown:** do not retry. The workspace remains readable; use a different approved disposable account only if the test owner authorizes it.

## Close the test

1. Sign out of the test account.
2. Remove any temporary personal notes that contain account or model output.
3. Label the result **Verified locally** or **Verified live** only if the complete authenticated observation succeeded. Otherwise label it **Not verified** and state the reason without including sensitive details.
