// The GoatCounter counting image (P6 item 6): the one request a page may make to another
// origin. GOATCOUNTER_CODE in packages/transform/scripts/build_state_pages.py sets the host.
export const COUNT_ORIGIN = 'https://curbcutng.goatcounter.com';

export function isVisitCount(url) {
  return url.startsWith(`${COUNT_ORIGIN}/count?`);
}
