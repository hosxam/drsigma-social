# DrSigma Instagram autopilot: daily runbook

This repo makes and publishes one post a day to Instagram @drsigma.emree (owner: Dr Hossam Abdelmageed, DrSigma, EMREE exam prep, drsigma.net). Posting is FULLY AUTOMATIC: Hossam chose not to review posts. That makes medical accuracy your job. When in doubt, choose a different, safer topic rather than post something uncertain.

## Fixed facts
- Audience: medical interns preparing for the EMREE (UAE licensing exam), in the UAE and abroad. Goals: reach, followers, sales.
- Product: drsigma.net. 14 books (7 High-Yield Reviews + 7 question banks), 4,900+ questions, filter by exam year, timed mocks in EMREE blueprint mix, every option explained, UAE guidance first. AED 400, one payment, 90 days, no subscription. 10 free pages at drsigma.net/try. Say "4,900+", never an exact count.
- Faceless brand. Never show Hossam's face or real people. No copyrighted characters, music, images or other creators' footage.
- Voice: confident "Sigma" mentor, dry humour, short sentences. No "bestie/slay" slang. No em dashes. Plain, human captions.
- Metricool brand: blogId `7807769`, timezone `Asia/Dubai`, network instagram.
- Media URL pattern: `https://raw.githubusercontent.com/hosxam/drsigma-social/main/media/<file>`

## Medical content rules (hard)
1. Every answer must be defensible from a guideline-grade source checked IN THIS RUN with WebSearch/WebFetch: NICE, ESC, ADA, ATLS, Resus Council UK, WHO, CDC, specialty societies, peer-reviewed consensus. Never Wikipedia, WikEM or blogs.
2. If a UAE guideline (DHA, DoH Abu Dhabi, MOHAP) covers the point, it wins over newer foreign guidance and is taught as the answer.
3. When guidelines disagree, the most recently published one wins.
4. Never invent statistics ("90% of interns get this wrong"). Hooks must be true without data.
5. Name the source in `sources` of the spec, and on the slide/explanation when it matters.
6. Topics marked "verify" in content/calendar.md must be verified against the UAE document or swapped out.

## Daily procedure (run in the evening; it prepares TOMORROW's post)
1. `cd` to this repo, `git pull`. Work out TOMORROW's date in Asia/Dubai. If `content/posts/<tomorrow>.json` exists AND its media is in `media/` AND Metricool already has a post scheduled for tomorrow (getScheduledPosts), stop: nothing to do except step 8.
2. Performance check: Metricool `getAnalyticsAvailableMetrics` / `getAnalyticsDataByMetrics` for instagram, last 14 days (or vidIQ `vidiq_ig_profile_reels` for @drsigma.emree, 5 credits). Note which series gets the most views/comments/shares.
3. Trend check (keep vidIQ spend to 1-2 calls, 5 credits each): `vidiq_instagram_tiktok_outlier_search` for medical-exam / med-student quiz or meme reels from the last 14 days. Borrow formats and hooks, never content.
4. Pick tomorrow's series from the weekly rhythm in content/calendar.md and the planned topic for that date. If a series is clearly winning (2x the others), it may take the Sat or Sun slot. Promo max once a week.
5. Write `content/posts/<tomorrow>.json` following the spec types in `studio/make.py` (copy an existing post as a template). Keep text short: stem <= 120 characters, options <= 40 characters each, explanation <= 170 characters. Increment the series number (see content/log.md).
6. Render: `python3 studio/make.py content/posts/<date>.json --frames`, then LOOK at the preview images with the Read tool. Fix any clipped, overlapping or overflowing text by shortening it, and re-check. Then render for real: `python3 studio/make.py content/posts/<date>.json`.
7. Publish: `git add -A && git commit -m "Post <date>: <slug>" && git push`. Confirm the raw URL returns the file (curl -sI may be blocked by the sandbox; if so trust a successful push). Then Metricool `createScheduledPost`:
   - date/publicationDate: `<tomorrow>T10:00:00`, timezone `Asia/Dubai`
   - providers `[{"network":"instagram"}]`, autoPublish true, draft false
   - reel: `instagramData: {"type":"REEL","showReelOnFeed":true,"isAiGenerated":false}` with the mp4 raw URL in `media`
   - carousel: `instagramData: {"type":"POST","isAiGenerated":false}` with all PNG raw URLs in order in `media`
   - `text` = the spec's caption
   If scheduling fails, retry once with fixed arguments; if it still fails, report the error clearly in the final message (Hossam gets a notification).
8. Append one line to `content/log.md`: date, series + number, topic, file, Metricool status, and yesterday's post views if available. Commit and push.
9. On Mondays also write `content/weekly-report.md` (overwrite): last 7 posts ranked by views, comments, shares; what to make more of; any change to the rhythm. Commit and push.
10. Final message: 3-5 lines. What was scheduled for when, the medical claim and its source, any problem.

## Never
- Post anything about real patients, real people, or identifiable cases.
- Reply to or delete comments, DM people, or change the profile.
- Change drsigma.net or any other repo.
- Run more than one post per day unless Hossam asks.
