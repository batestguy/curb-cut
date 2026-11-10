// Connect to the open browser, run one action file, print a short page summary.
import { chromium } from "playwright";
import { pathToFileURL } from "node:url";
const browser = await chromium.connectOverCDP("http://127.0.0.1:9333");
const page = browser.contexts()[0].pages().at(-1);
const mod = await import(pathToFileURL(process.argv[2]).href);
await mod.default(page);
console.log("URL:", page.url());
await browser.close(); // disconnects only; the window stays open
