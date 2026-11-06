// The chart's description in Hausa, Yoruba, Igbo and Nigerian Pidgin (P6 item 8), as a
// <details> under the chart. The same markup as the state pages, which have no script
// (packages/transform/scripts/translations.py, disclosure_html): an English note, then for
// each language a visible label ("Hausa: drafted by AI, not reviewed by a native speaker"),
// its note and the description, each marked with its lang. The texts come from the chart
// document's alt_text_translations (built and audited by disability-access-charts); the
// disclosure's own words from data/translations.json (packages/transform/translations.yml).

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  node.append(...children);
  return node;
}

/**
 * The disclosure for `doc`, or null when the document has no translations. Throws if a
 * language in `ui` has no translation, or a translation is marked reviewed (the label says
 * it is not).
 */
export function translationsDisclosure(doc, ui) {
  const block = doc.alt_text_translations;
  if (!block || Object.keys(block).length === 0) return null;
  const details = el(
    'details',
    { class: 'translations' },
    el('summary', {}, ui.summary),
    el('p', { class: 'translations-note' }, ui.note),
  );
  for (const lang of ui.languages) {
    const entry = block[lang.code];
    if (!entry) throw new Error(`no ${lang.code} translation for ${doc.id}`);
    if (entry.reviewed !== false) throw new Error(`the ${lang.code} text of ${doc.id} is marked reviewed`);
    details.append(
      el(
        'div',
        { class: 'translation' },
        el('p', { class: 'translation-label' }, el('strong', {}, lang.name), `: ${ui.label}`),
        el('p', { class: 'translation-note', lang: lang.code }, lang.note),
        el('p', { class: 'translation-text', lang: lang.code }, entry.text),
      ),
    );
  }
  return details;
}

/** Put the disclosure for `doc` into `holder` (emptied first); nothing if it has none. */
export function placeTranslations(holder, doc, ui) {
  if (!holder) return;
  const details = ui ? translationsDisclosure(doc, ui) : null;
  holder.replaceChildren(...(details ? [details] : []));
}
