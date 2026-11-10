export default async (page) => {
  await page.fill("#givenName", "Jerry");
  await page.fill("#familyName", "Bannister");
  await page.fill("#affiliation", "Abubakar Tafawa Balewa University, Bauchi");
  await page.selectOption("#country", { label: "Nigeria" });
  await page.fill("#email", "jzbannister@atbu.edu.ng");
  await page.fill("#username", "jzbannister");
  await page.focus("#password");
  for (const id of ["givenName", "familyName", "affiliation", "country", "email", "username"])
    console.log(id, "=", await page.inputValue("#" + id));
};
