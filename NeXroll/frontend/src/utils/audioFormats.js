export const AUDIO_FORMATS = [
  ['ac3', 'Dolby Digital'], ['eac3', 'Dolby Digital Plus'], ['truehd', 'Dolby TrueHD'],
  ['dts', 'DTS / DTS-HD'], ['aac', 'AAC'], ['flac', 'FLAC'], ['pcm', 'PCM'],
  ['mp3', 'MP3'], ['opus', 'Opus'], ['vorbis', 'Vorbis'],
];
export const audioLabel = value => AUDIO_FORMATS.find(([key]) => key === value)?.[1] || value;
