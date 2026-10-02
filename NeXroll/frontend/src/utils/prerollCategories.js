/**
 * Which categories a preroll is in, read the same way everywhere.
 *
 * The many-to-many `categories` list is canonical: playback, schedules and the
 * API's category filter all read it. `category_id` is the older single
 * "primary" field. It is kept for older rows, and deleting a category clears it
 * on every preroll that had it as primary while their other categories remain,
 * so a preroll can have categories and no primary. `category_ids` is only sent
 * when saving; the API never returns it.
 *
 * Counting with `category_id` alone (or `category_ids`) reported such prerolls
 * as uncategorized: issue #45, a Library with every preroll categorized showed
 * "Needs category 66".
 */

/** Every category id a preroll is in, primary first, without duplicates. */
export const prerollCategoryIds = (preroll) => {
  const ids = [];
  const add = (value) => {
    if (value === null || value === undefined || value === '') return;
    const id = Number(value);
    if (Number.isFinite(id) && !ids.includes(id)) ids.push(id);
  };
  add(preroll?.category_id);
  (Array.isArray(preroll?.categories) ? preroll.categories : []).forEach(category => add(category?.id));
  return ids;
};

/** True when a preroll is in no category at all. */
export const isUncategorized = (preroll) => prerollCategoryIds(preroll).length === 0;

/** True when a preroll is in the category, as primary or otherwise. */
export const prerollInCategory = (preroll, categoryId) => {
  if (categoryId === null || categoryId === undefined || categoryId === '') return false;
  return prerollCategoryIds(preroll).includes(Number(categoryId));
};

/** The category to list a preroll under: its primary, else its first category, else null. */
export const displayCategoryId = (preroll) => {
  const [first] = prerollCategoryIds(preroll);
  return first === undefined ? null : first;
};

/** Names of every category a preroll is in, primary first. */
export const prerollCategoryLabels = (preroll, categories = []) => prerollCategoryIds(preroll)
  .map(id => (preroll?.categories || []).find(c => Number(c?.id) === id)?.name
    || (Number(preroll?.category?.id) === id ? preroll.category.name : null)
    || categories.find(c => Number(c?.id) === id)?.name)
  .filter(Boolean);
