import { act, renderHook } from '@testing-library/react';
import useHealthSummary from './useHealthSummary';

const healthy = { score: 100, status: 'healthy', attention_count: 0, checks: [] };
const offline = { score: 70, status: 'degraded', attention_count: 1,
  note: 'No connection to media server (Jellyfin)',
  checks: [{ key: 'media_server', status: 'error' }] };
const reply = data => Promise.resolve({ ok: true, json: async () => data });
const flush = async () => { await act(async () => {}); };

beforeEach(() => { jest.useFakeTimers(); global.fetch = jest.fn(); });
afterEach(() => { jest.useRealTimers(); delete global.fetch; });

test('polls an unchanged dashboard through shutdown and recovery', async () => {
  fetch.mockImplementationOnce(() => reply(healthy))
    .mockImplementationOnce(() => reply(offline))
    .mockImplementationOnce(() => reply(healthy));
  const { result, unmount } = renderHook(() => useHealthSummary('/health', true, 1, 1));
  await flush();
  expect(result.current.status).toBe('healthy');
  await act(async () => { jest.advanceTimersByTime(30000); });
  expect(result.current.note).toContain('No connection to media server');
  await act(async () => { jest.advanceTimersByTime(30000); });
  expect(result.current.status).toBe('healthy');
  unmount();
  jest.advanceTimersByTime(60000);
  expect(fetch).toHaveBeenCalledTimes(3);
});

test('failed refresh replaces stale healthy status and retries on focus', async () => {
  fetch.mockImplementationOnce(() => reply(healthy))
    .mockRejectedValueOnce(new Error('offline'))
    .mockImplementationOnce(() => reply(healthy));
  const { result } = renderHook(() => useHealthSummary('/health', true, 1, 1));
  await flush();
  await act(async () => { jest.advanceTimersByTime(30000); });
  expect(result.current.status).toBe('attention');
  expect(result.current.note).toContain('Unable to refresh');
  await act(async () => { window.dispatchEvent(new Event('focus')); });
  expect(result.current.status).toBe('healthy');
});

test('does not overlap probes and aborts a hung request', async () => {
  fetch.mockImplementation((url, { signal }) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const { result, unmount } = renderHook(() => useHealthSummary('/health', true, 1, 1));
  act(() => window.dispatchEvent(new Event('focus')));
  expect(fetch).toHaveBeenCalledTimes(1);
  await act(async () => { jest.advanceTimersByTime(12000); });
  expect(result.current.status).toBe('attention');
  await act(async () => { jest.advanceTimersByTime(18000); });
  expect(fetch).toHaveBeenCalledTimes(2);
  const signal = fetch.mock.calls[1][1].signal;
  unmount();
  expect(signal.aborted).toBe(true);
});

test('changed inputs discard an older in-flight response', async () => {
  let resolveOld;
  fetch.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }))
    .mockImplementationOnce(() => reply(offline));
  const { result, rerender } = renderHook(({ url }) => useHealthSummary(url, true, 1, 1),
    { initialProps: { url: '/health?conflicts=0' } });
  rerender({ url: '/health?conflicts=1' });
  await flush();
  await act(async () => { resolveOld({ ok: true, json: async () => healthy }); });
  expect(result.current.status).toBe('degraded');
});
