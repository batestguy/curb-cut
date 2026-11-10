export default async (page) => {
  await page.getByRole("link", { name: "Make a New Submission" }).click();
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForTimeout(3000);
  console.log("TITLE:", await page.title());
  const t = (await page.innerText("main, body")).replace(/\s+/g, " ");
  const s = t.indexOf("Submit");
  console.log(t.slice(0, 3000));
  const fields = await page.$$eval("input, select, textarea, button", (els) =>
    els.filter((e) => e.type !== "hidden").map((e) => [e.tagName, e.type, e.name || e.id, (e.labels?.[0]?.innerText || e.innerText || e.getAttribute("aria-label") || "").trim().slice(0, 90)])
  );
  for (const f of fields) console.log(JSON.stringify(f));
};
