# DrSigma skit factory: runbook

Hossam's decision (17 Nov 2026): the account switches to AI NPC vs SIGMA comedy skits made with Higgsfield, one reel a day at 10:00 Asia/Dubai, fully automatic, no manual review. The old quiz autopilot and its week-1 posts are retired. The 30 skits for 19 Nov to 18 Dec are in `content/skits/concepts.json`; 18 Nov is skit #01 (already made).

The factory run makes every missing skit in one go, back to back, then schedules them all in Metricool. It is safe to re-run: it only does what is missing.

## Hard rules
- NO MUSIC, ever. Generate with `generate_audio: false`. `studio/skit.py` drops the clip's audio anyway and adds synthesized sound effects only.
- Higgsfield: pay ONLY with the free unlimited allowance (`use_unlim: true`). Never spend credits, never buy anything, never touch the trial or its auto-renewal. If unlimited is not available (it expires 20 Nov 2026), stop generating and notify Hossam with how many skits are done and how many are missing.
- Faceless brand: only the clay NPC and SIGMA characters and clay extras. No real people, no copyrighted characters, logos or music.
- Medical facts: a concept with a `fact` must be verified in THIS run with WebSearch/WebFetch against the source named in `fact.check` (or a newer guideline-grade source: NICE, Resus Council UK, ATLS, ADA, specialty society; a UAE DHA/DoH/MOHAP document wins if it covers the point). Never Wikipedia, WikEM or blogs. If it doesn't hold up, fix the wording to match the guideline or replace the skit with a humour-only one. Never invent statistics.
- Instagram `isAiGenerated: true` on every skit.
- Never reply to comments, DM, change the profile, touch drsigma.net or any other repo. One post per day.

## Steps
1. `cd` to the repo, `git pull`. Read `content/skits/concepts.json` and `content/skits/log.md`.
2. Work out what is missing: a skit is DONE when `media/<date>_skit-<NN>_<slug>.mp4` exists in the repo AND Metricool has a non-draft scheduled post on that date at 10:00 whose media is that file. Skip dates already in the past.
3. Character references: upload `assets/characters/npc.png` and `assets/characters/sigma.png` to Higgsfield once per run (`media_upload`, PUT, `media_confirm`). If the upload fails, go on with text-only prompts.
4. Generate the clips for every missing skit. Model `seedance_2_5`, `mode: "omni_reference"` with both refs as `image_references` (or `mode: "t2v"` if refs failed), `aspect_ratio: "9:16"`, `duration: 10`, `resolution: "720p"`, `generate_audio: false`, `use_unlim: true`. Prompt = the skit's `prompt` + " " + the bank's `style`.
   - Submit up to 3 jobs at a time; keep a queue. On a 429 rate-limit, wait 2-5 minutes and try that one again (sleep in steps under 2 minutes). Don't resubmit a job whose outcome is unknown; check it with `jobs_wait` first.
   - Poll with `jobs_wait`; download each finished clip to `content/skits/raw/<date>_raw.mp4` as it lands.
   - Commit and push raw clips every few skits so a crash doesn't lose work.
   - A clip that fails, is flagged, or comes back broken gets ONE retry; then mark it failed in the log and move on.
5. Finish each clip:
   - Extract a contact sheet (frames at 1, 3, 5, 7, 9 s) and LOOK at it with Read. Reject and regenerate (once) if: a character is missing, there's garbled on-screen text that matters, gore, nudity, a real-looking person, or the joke doesn't read.
   - Write `content/skits/specs/<date>.json` (copy `content/skits/specs/2026-11-18.json`): fill from the concept, set `raw`, `job_id`, `labels` (`[["NPC",0.25],["SIGMA",0.75]]` when the concept says labels true, else `[]`), convert `beats` to `{"t","text"}` and RETIME beats/fx/sfx to the real action in the clip.
   - `python3 studio/skit.py content/skits/specs/<date>.json --frames`, LOOK at the preview, fix clipped or overlapping text by shortening it, then render for real without `--frames`.
6. Publish: `git add -A && git commit && git push` (commit messages end with `Co-Authored-By: Claude <noreply@anthropic.com>`). Media URL: `https://raw.githubusercontent.com/hosxam/drsigma-social/main/media/<file>`.
7. Schedule each finished skit in Metricool (blogId `7807769`): `<date>T10:00:00`, timezone `Asia/Dubai`, providers `[{"network":"instagram"}]`, autoPublish true, draft false, `instagramData: {"type":"REEL","showReelOnFeed":true,"isAiGenerated":true}`, media = the raw URL, text = the concept caption (with any wording fixed during verification).
   - If Metricool already has a post on that date at 10:00 (the retired quiz posts for 19-24 Nov, now drafts), UPDATE that post with `updateScheduledPost` (keep its uuid, set the new text, media, draft false, isAiGenerated true) instead of creating a second one. Exactly one post per date.
8. Append one line per skit to `content/skits/log.md`: date, #, slug, job id, fact + source checked (or "humour"), Metricool post id, status. Commit and push.
9. Notify Hossam (PushNotification) ONLY with: how many skits are scheduled and through which date, any skit that failed or was swapped, and any fact that had to change. If everything was already done, stay silent.
