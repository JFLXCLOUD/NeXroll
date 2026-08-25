import {
  getCommunityCategorySelection,
  setCommunityCategorySelection
} from './communityCategorySelection';

describe('Community Preroll category selections', () => {
  it('keeps each open preroll dropdown independent', () => {
    const firstSelected = setCommunityCategorySelection({}, 101, '4');
    const bothSelected = setCommunityCategorySelection(firstSelected, 202, '9');

    expect(getCommunityCategorySelection(bothSelected, 101)).toBe('4');
    expect(getCommunityCategorySelection(bothSelected, 202)).toBe('9');
  });

  it('clears only the downloaded preroll selection', () => {
    const selections = { 101: '4', 202: '9' };
    const afterDownload = setCommunityCategorySelection(selections, 101, null);

    expect(afterDownload).toEqual({ 202: '9' });
    expect(selections).toEqual({ 101: '4', 202: '9' });
  });

  it('treats numeric and string preroll IDs as the same item', () => {
    const selections = setCommunityCategorySelection({}, 101, '4');

    expect(getCommunityCategorySelection(selections, '101')).toBe('4');
  });
});
