/** Local-timezone-aware helpers for round-tripping timezone-aware ISO instants
 * through `<input type="date">` / `<input type="datetime-local">` fields.
 *
 * `datetime-local` inputs read and write local wall-clock time with no
 * timezone info, so a stored UTC instant must be converted to local
 * components before display (never sliced off the raw UTC string) and local
 * input values must be converted back to an absolute instant on save.
 */

export function localInputValue(iso: string): string {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function localDateValue(iso: string): string {
  return localInputValue(iso).slice(0, 10);
}

export function combineLocalDateTime(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString();
}
