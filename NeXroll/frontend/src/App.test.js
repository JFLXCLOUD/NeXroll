import { render, screen } from '@testing-library/react';

jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }) => children
}));

import App from './App';

beforeEach(() => {
  // Keep backend-dependent startup checks pending so this remains a focused,
  // deterministic render smoke test for the initial application shell.
  global.fetch = jest.fn(() => new Promise(() => {}));
  window.matchMedia = jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn()
  }));
});

afterEach(() => {
  delete global.fetch;
  delete window.matchMedia;
});

test('renders the NeXroll boot splash while startup checks are pending', () => {
  const { container } = render(<App />);
  expect(container.querySelector('.spin')).toBeInTheDocument();
  expect(screen.queryByText(/learn react/i)).not.toBeInTheDocument();
});
