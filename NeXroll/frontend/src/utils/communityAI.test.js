import { isAICommunitySource } from './communityAI';

test.each([
  '/AI/Movie%20Night%20-%20CommunicationFit3862/Movie%20Night%20-%20Plex.mp4',
  '/ai/intro.mp4', '/%41%49/intro.mp4',
  'https://uk.prerolls.uk/AI/Movie%20Night.mp4',
  'https://prerolls.video/%41%49/intro.mp4',
])('recognizes saved Community AI source %s', source => {
  expect(isAICommunitySource(source)).toBe(true);
});

test.each([null, undefined, '', 42, '/Community/AI Collection/intro.mp4',
  '/Community/Rain/intro.mp4', '/AI-generated.mp4', '/%ZZ/intro.mp4',
  'https://ai.example/Community/intro.mp4', 'https://prerolls.video/Community/intro.mp4?folder=/AI/',
])('does not infer AI from unrelated or missing source %s', source => {
  expect(isAICommunitySource(source)).toBe(false);
});
