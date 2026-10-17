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
- [ ] The state picker works with arrow keys or by typing a state name. The state table appears.
- [ ] Nothing needs a mouse: no hover-only information, and no focus traps.
- [ ] At 400% browser zoom (Ctrl + plus), nothing is cut off and there is no sideways scrolling.

## 2. NVDA

- [ ] **Insert+Down arrow** (read all): the page reads in a sensible order; press **Ctrl** to stop.
- [ ] **H** / **Shift+H**: headings make sense on their own and describe the page structure.
- [ ] **G**: the chart is announced once, with a description that gives the key numbers. It is not read twice, and no SVG noise is read.
- [ ] **T**: the table caption is read. Inside the table, **Ctrl+Alt+arrow keys** announce the column and row headers with each number.
- [ ] **Tab** to the state picker: its label ("State") is read. Changing the state announces loading and then "Showing 10 disability types for …".
- [ ] Error and loading messages are spoken without moving focus.
- [ ] Nothing important is silent, and nothing is repeated so often that it gets in the way.

## Record

For each gate, write in `docs/STATUS.md`: date, tester, browser, screen reader and version, what passed, what was confusing, and what was fixed.
