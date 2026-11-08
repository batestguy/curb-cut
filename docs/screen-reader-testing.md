# Screen-reader testing: "Can you find what you need?"

Sessions with people who use a screen reader every day, the check that `PLAN.md` (P6 gate) seeks before launch. Automated tests, keyboard checks and the author's NVDA pass have run; none of them replaces a regular screen-reader user. The author runs the sessions; this page is the kit and the record. Until the first session is done, the site keeps saying it has not been tested by a regular screen-reader user.

## Who (3–5 people)

| # | Who | Why |
|---|---|---|
| 1–2 | Blind people who use NVDA or JAWS on a computer every day | The site's main desktop audience; NVDA is free and common in Nigeria |
| 3 | A blind person who uses TalkBack (Android) or VoiceOver (iPhone) on a phone | Most Nigerians reach the web by phone |
| 4 | A person with low vision who uses magnification or high contrast | Zoom, contrast and reflow problems that screen-reader tests miss |
| 5 (optional) | Someone at JONAPWD, a state chapter of the Nigeria Association of the Blind, or a disability organisation who uses a screen reader at work | They would use the figures in advocacy |

Ask through JONAPWD, a state chapter of the Nigeria Association of the Blind, a university's disability or special-education unit, or an NVDA users' group. Try to include at least one woman and one person outside Bauchi.

## Invitation (WhatsApp or email)

> Hello [name], I'm Jerry Bannister, a statistician in Bauchi and a wheelchair user. I've built Curb Cut, a free website with measured disability figures for every Nigerian state, made to work with screen readers. It has not yet been tried by someone who uses a screen reader every day, and I'd like to learn what works and what doesn't. Could you spare 30 minutes this week or next, by phone or WhatsApp call while you use the site with your own screen reader? I'll take notes, not a recording, and I won't use your name unless you say I can. There is no payment; with your permission I'd thank you by name on the site.

## The session (30 minutes)

**Before:** send the link https://batestguy.github.io/curb-cut/ only when the call starts. Ask which screen reader, browser and device they use, and which settings they normally change (speech rate, verbosity).

1. **Consent (read out):** "I'll take notes, not a recording. I'll write down your screen reader and device, not your name, unless you say I can. You can stop at any time, and nothing you say is a test of you: it's a test of the site." Record the answer.
2. **Task 1, 8 minutes: "Find the disability figure for your own state."** Don't explain how. Note the route they take (headings, links, the state picker, the state pages) and where they hesitate.
3. **Task 2, 8 minutes: "On the main page, find which states are in the highest group on the map."** (The map key's buttons announce the states in a range.) Note whether they find the key, what they hear when they press a range, and whether the table is easier.
4. **Task 3, 8 minutes: "Is disability more common among people who are poor? Find what the site says."** (The "Disability and poverty" page.) Note whether the answer and its caution ("an association, not proof of cause") come through.
5. **Questions, 5 minutes:**
   - "What was the most confusing or annoying moment?"
   - "Was anything read twice, or not read at all?"
   - "Is there something you expected to find and didn't?"
   - "Would you use this site, and for what?"
6. **Close:** "May I contact you again when I've fixed what you found? And may I thank you by name on the site?" Record both answers.

Say as little as possible during the tasks. If they are stuck for two minutes, ask "What are you looking for?" and note it as a finding rather than helping straight away.

## Notes (one row per session)

| Date | Screen reader, browser, device | State | Task 1: route and problems | Task 2 | Task 3 | Answers to the questions (their words) | Named with consent? | Recontact OK? |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Keep personal details out of this file. Contact details stay in the author's phone, not in the repository (Nigeria Data Protection Act 2023: collect only what's needed). If someone agrees to be named, record "named with consent (date)".

## What happens next

1. List every problem found, with how many people hit it and how badly (blocked, slowed, annoyed).
2. Fix the blockers first, each in its own pull request that cites this page.
3. Ask the people who found them to try the fix, if they agreed to be contacted.
4. When at least one session is done, change the site's sentence "has not yet been tested by a regular screen-reader user" to say what was tested, when, and with which screen readers, and record it in `docs/STATUS.md`.
