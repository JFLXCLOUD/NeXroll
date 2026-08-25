// Category choices belong to an individual Community Preroll. Keeping the
// update logic here makes that isolation explicit and directly testable.
export const getCommunityCategorySelection = (selections, prerollId) =>
  selections?.[String(prerollId)] ?? null;

export function setCommunityCategorySelection(selections, prerollId, categoryId) {
  const next = { ...(selections || {}) };
  const key = String(prerollId);

  if (categoryId === null || categoryId === undefined || categoryId === '') {
    delete next[key];
  } else {
    next[key] = categoryId;
  }

  return next;
}
