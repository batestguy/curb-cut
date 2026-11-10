export default async (page) => {
  console.log("TITLE:", await page.title());
  const t = (await page.innerText("body")).replace(/\s+/g, " ");
  console.log(t.slice(0, 900));
};
