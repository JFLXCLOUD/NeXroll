import {
  displayCategoryId,
  isUncategorized,
  prerollCategoryIds,
  prerollCategoryLabels,
  prerollInCategory,
} from './prerollCategories';

// Issue #45: what the API returns for a preroll whose primary category was
// deleted while it stayed in Halloween.
const halloweenOnly = { category_id: null, category: null, categories: [{ id: 5, name: 'Halloween' }] };
const legacyOnly = { category_id: 3, category: { id: 3, name: 'Intros' }, categories: [] };
const both = { category_id: 3, category: { id: 3, name: 'Intros' }, categories: [{ id: 3, name: 'Intros' }, { id: 5, name: 'Halloween' }] };
const none = { category_id: null, category: null, categories: [] };

test('a preroll with only a non-primary category is categorized', () => {
  expect(isUncategorized(halloweenOnly)).toBe(false);
  expect(prerollInCategory(halloweenOnly, 5)).toBe(true);
  expect(displayCategoryId(halloweenOnly)).toBe(5);
});

test('an older row with only the primary field is categorized', () => {
  expect(isUncategorized(legacyOnly)).toBe(false);
  expect(prerollInCategory(legacyOnly, 3)).toBe(true);
});

test('only a preroll with no category at all is uncategorized', () => {
  expect(isUncategorized(none)).toBe(true);
  expect(isUncategorized({ category_ids: [] })).toBe(true);
  expect(displayCategoryId(none)).toBeNull();
  // category_ids is never returned by the API and must not matter.
  expect(isUncategorized({ ...halloweenOnly, category_ids: undefined })).toBe(false);
});

test('ids are listed primary first without duplicates, and string ids match', () => {
  expect(prerollCategoryIds(both)).toEqual([3, 5]);
  expect(prerollInCategory(both, '5')).toBe(true);
  expect(prerollInCategory(both, 9)).toBe(false);
  expect(prerollInCategory(both, null)).toBe(false);
});

test('names come from the preroll, falling back to the category list', () => {
  expect(prerollCategoryLabels(both)).toEqual(['Intros', 'Halloween']);
  expect(prerollCategoryLabels(halloweenOnly)).toEqual(['Halloween']);
  expect(prerollCategoryLabels({ category_id: 7 }, [{ id: 7, name: 'Kids' }])).toEqual(['Kids']);
  expect(prerollCategoryLabels(none)).toEqual([]);
});
