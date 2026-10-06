import React from 'react';
import ChipPicker from './ChipPicker';
import { useLibraryGenres, useLibraryTags } from '../utils/sequenceConditions';

// Offered when no Jellyfin/Emby library can be asked; typed names still work.
const COMMON_GENRES = ['Action', 'Animation', 'Comedy', 'Documentary', 'Drama', 'Family', 'Fantasy', 'Horror', 'Romance', 'Science Fiction', 'Thriller'];

/**
 * GenrePicker - chooses the genres a genre rule matches. Suggestions come from
 * the connected Jellyfin/Emby libraries, so they match the names those servers
 * actually use; any name can still be typed. Matching is case-insensitive.
 */
const GenrePicker = ({ values = [], onChange }) => {
  const library = useLibraryGenres();
  return (
    <ChipPicker
      values={values}
      onChange={onChange}
      suggestions={library.length ? library : COMMON_GENRES}
      placeholder="e.g. Horror"
      morePlaceholder="Add another genre"
      label="Genre"
      hint={library.length === 0 ? "Connect Jellyfin or Emby to pick from your library's own genre names." : null}
    />
  );
};

/** TagPicker - the same for a tag rule, suggesting the libraries' own tags. */
export const TagPicker = ({ values = [], onChange }) => {
  const library = useLibraryTags();
  return (
    <ChipPicker
      values={values}
      onChange={onChange}
      suggestions={library}
      placeholder="e.g. IMAX"
      morePlaceholder="Add another tag"
      label="Tag"
      hint={library.length === 0 ? 'Type a tag exactly as Jellyfin or Emby shows it (capitals don\'t matter).' : null}
    />
  );
};

/** FilePathPicker - text a file path rule looks for. No suggestions. */
export const FilePathPicker = ({ values = [], onChange }) => (
  <ChipPicker
    values={values}
    onChange={onChange}
    placeholder="e.g. IMAX"
    morePlaceholder="Add more text to look for"
    label="Text in the file path"
  />
);

export default GenrePicker;
