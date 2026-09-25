export const TRAILER_RATINGS = ['G', 'PG', 'PG-13', 'R', 'NC-17', 'TV-Y', 'TV-Y7', 'TV-Y7-FV', 'TV-G', 'TV-PG', 'TV-14', 'TV-MA', 'Unrated'];

export const hasRatingFilter = value => value?.restrict_ratings === true || (Array.isArray(value?.ratings) && value.ratings.length > 0);
export const ratingSummary = value => hasRatingFilter(value)
  ? `ratings: ${(value.ratings || []).join(', ') || 'none selected'}` : '';
