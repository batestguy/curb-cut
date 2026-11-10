export default async (page) => {
  for (const id of ["givenName", "email", "username"]) console.log(id, "=", await page.inputValue("#" + id));
  console.log("password filled:", (await page.inputValue("#password")).length > 0);
  console.log("consent ticked:", await page.isChecked("input[name=privacyConsent]"));
  const errs = await page.$$eval(".pkp_form_error, .error, [role=alert]", (e) => e.map((x) => x.innerText.trim()).filter(Boolean));
  console.log("errors:", JSON.stringify(errs));
};
