export default async (page) => {
  await page.waitForLoadState("domcontentloaded");
  const fields = await page.$$eval("input, select, textarea, button", (els) =>
    els.map((e) => [e.tagName, e.type, e.name, e.id, (e.labels?.[0]?.innerText || e.innerText || "").trim().slice(0, 60), e.required])
  );
  for (const f of fields) console.log(JSON.stringify(f));
};
