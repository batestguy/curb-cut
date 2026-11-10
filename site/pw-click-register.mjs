export default async (page) => {
  await Promise.all([
    page.waitForLoadState("load").catch(() => {}),
    page.getByRole("button", { name: "Register", exact: true }).click(),
  ]);
  await page.waitForTimeout(4000);
  console.log("TITLE:", await page.title());
  const t = (await page.innerText("body")).replace(/\s+/g, " ");
  const m = t.match(/[^.]*(error|already|invalid|match|registration|thank|confirm|validat)[^.]*\./gi);
  console.log("MSGS:", JSON.stringify(m?.slice(0, 8)));
};
