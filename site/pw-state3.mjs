export default async (page) => {
  for (const p of page.context().pages()) console.log("TAB:", p.url());
  const t = (await page.innerText("body")).replace(/\s+/g, " ");
  const i = t.indexOf("Repeat password");
  console.log("AROUND FORM:", t.slice(Math.max(0, t.indexOf("Afghanistan") - 50), t.indexOf("Afghanistan")));
  console.log("TAIL:", t.slice(i, i + 900));
  const m = t.match(/[^.]*(error|already|invalid|match|captcha|robot)[^.]*\./gi);
  console.log("MSGS:", JSON.stringify(m));
  console.log("password filled:", (await page.inputValue("#password")).length > 0, "consent:", await page.isChecked("input[name=privacyConsent]"));
  console.log("frames:", page.frames().map((f) => f.url()).filter((u) => u && u !== "about:blank"));
};
