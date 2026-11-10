import { chromium } from "playwright";
const ctx = await chromium.launchPersistentContext(process.argv[2], {
  headless: false,
  channel: "msedge",
  viewport: null,
  args: ["--remote-debugging-port=9333", "--start-maximized"],
});
const page = ctx.pages()[0] ?? (await ctx.newPage());
await page.goto("https://dcidj.uog.edu.et/index.php/up-j-dcbrid/user/register");
console.log("browser open");
await new Promise((resolve) => ctx.on("close", resolve));
