# Manual accessibility test script

Automated checks (axe in Playwright, and Lighthouse from P6) catch only part of the problems. Use this script for the manual check at each gate that changes the site, and write the results in `docs/STATUS.md`.

Two kinds of manual check feed the gates:

1. **Author check, every gate:** keyboard only, then NVDA, following the steps below. The author is new to screen readers, so this is a first-time user's check. It catches broken or confusing behaviour, not expert-user friction.
2. **Regular screen-reader user, before launch (P6 gate):** at least one person who uses NVDA or JAWS daily tries the site and gives feedback, and the fixes are made. Find them through JONAPWD, a blind persons' association, or an NVDA user community. Credit them only with their permission.

## Setup

- **NVDA** (NonVisual Desktop Access): a free screen reader for Windows from https://www.nvaccess.org (the donation is optional).
  - **Ctrl+Alt+N** starts NVDA. **Insert+Q** quits it.
  - "NVDA key" means **Insert**.
  - Press **Ctrl** at any time to stop speech.
- Test in the browser you normally use (Brave/Chrome), and in Firefox if possible.
- No NVDA? Windows **Narrator** (Ctrl+Windows+Enter) is a fallback. Record which one you used.

## 1. Keyboard only (no screen reader, mouse unplugged or untouched)

- [ ] **Tab** from the top of the page: the first stop is "Skip to main content", and it is visible when focused.
- [ ] **Enter** on the skip link moves focus into the main content.
- [ ] Every link and control can be reached with **Tab** and **Shift+Tab**, in a sensible order, and there is always a visible focus outline.
- [ ] **Tab** to the state picker. Type **Lagos** (or use **Down arrow**): nothing loads yet. Press **Tab** to reach **Show figures**, then **Enter**.
- [ ] After a few seconds the first time, a state card appears with the heading "Lagos", and focus (the outline) is on that heading. The card shows the capital, zone, 2023 population, slogan, JONAPWD's estimate with share and rank, a map with Lagos filled green, outlined and circled, and a "Sources" line. The Lagos table follows below the card.
- [ ] In the "All types, by state" chart above, the Lagos bar is now a different colour, outlined, with a bold label. Choose **Kano** and press **Show figures** again: the highlight moves to Kano.
- [ ] **Tab** from the card heading reaches the source links in the card (NBS, Wikipedia, Zikoko), each with a visible focus outline.
- [ ] Choose **Ekiti** and press **Show figures**: the card has no slogan line (no sourced slogan), and nothing else is missing.
- [ ] Nothing needs a mouse: no hover-only information, and no focus traps.
- [ ] At 400% browser zoom (Ctrl + plus), nothing is cut off and there is no sideways scrolling. The state card stacks: facts first, then the map.
- [ ] The green-white-green band at the top of the page is visible in both light and dark mode (Windows: Settings → Personalisation → Colours → "Choose your mode").

## 2. NVDA

- [ ] **Insert+Down arrow** (read all): the page reads in a sensible order; press **Ctrl** to stop.
- [ ] **H** / **Shift+H**: headings make sense on their own and describe the page structure.
- [ ] **G** (and **G** again): each of the two charts is announced once, with a description that gives the key numbers. Neither is read twice, and no SVG noise is read.
- [ ] **T**: the table caption is read. Inside the table, **Ctrl+Alt+arrow keys** announce the column and row headers with each number.
- [ ] **Tab** to the state picker: its label ("State") is read, as a combo box. Moving through states with the arrow keys reads each name and loads nothing.
- [ ] **Tab** to **Show figures** and press **Enter**: "Loading figures for Lagos…" is spoken. When it finishes, NVDA reads the heading "Lagos" (focus moves there). Whether "Showing 10 disability types for Lagos." is also spoken: note what you hear.
- [ ] From the "Lagos" heading, **Down arrow** reads the card in order: the facts as a list of terms and values, the share and rank sentence, then "Map of Nigeria with Lagos highlighted, in the South West zone" (read once as a graphic, no SVG noise), "Boundaries: geoBoundaries (CC BY 4.0)", the sources line, then the Lagos table.
- [ ] Choose **Kano**, then **Show figures**: NVDA reads the heading "Kano". The chart's description does not change (the bar highlight is visual only; the card says the same thing in words).
- [ ] Error and loading messages are spoken without moving focus.
- [ ] Nothing important is silent, and nothing is repeated so often that it gets in the way.

## Record

For each gate, write in `docs/STATUS.md`: date, tester, browser, screen reader and version, what passed, what was confusing, and what was fixed.
