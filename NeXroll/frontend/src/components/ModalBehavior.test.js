import { fireEvent, render, screen } from '@testing-library/react';
import BlockEditor from './BlockEditor';
import PatternExport from './PatternExport';
import PatternImport from './PatternImport';
import SequencePreviewModal from './SequencePreviewModal';

describe('standalone modal behavior', () => {
  beforeEach(() => {
    global.fetch = jest.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve([]),
    }));
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('sequence preview exposes a visible close control and closes on Escape', () => {
    const onClose = jest.fn();
    render(
      <SequencePreviewModal
        isOpen
        onClose={onClose}
        blocks={[]}
        categories={[]}
        prerolls={[]}
        apiUrl={(path) => path}
      />
    );

    const closeButton = screen.getByRole('button', { name: /close sequence preview/i });
    expect(closeButton).not.toBeEmptyDOMElement();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('Escape closes only the topmost stacked sequence preview', () => {
    const parentClose = jest.fn();
    const childClose = jest.fn();
    render(
      <>
        <SequencePreviewModal isOpen onClose={parentClose} blocks={[]} apiUrl={(path) => path} />
        <SequencePreviewModal isOpen onClose={childClose} blocks={[]} apiUrl={(path) => path} />
      </>
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(parentClose).not.toHaveBeenCalled();
    expect(childClose).toHaveBeenCalledTimes(1);
  });

  test('export dialog has dialog semantics and closes on Escape while idle', () => {
    const onClose = jest.fn();
    render(
      <PatternExport
        isOpen
        onClose={onClose}
        scheduleId={1}
        scheduleName="Test sequence"
      />
    );

    expect(screen.getByRole('dialog', { name: /export sequence pattern/i })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('import dialog has an accessible close control', () => {
    // Keep the background category request pending; this test exercises only
    // the initial dialog controls and should not race an unrelated state update.
    global.fetch.mockImplementationOnce(() => new Promise(() => {}));
    render(<PatternImport isOpen onClose={jest.fn()} onImport={jest.fn()} />);
    expect(screen.getByRole('dialog', { name: /import sequence pattern/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /close import dialog/i })).toBeEnabled();
  });

  test('block editor closes on Escape', () => {
    const onCancel = jest.fn();
    render(
      <BlockEditor
        block={{ id: 'new-block', type: 'random' }}
        categories={[]}
        prerolls={[]}
        isNew
        onSave={jest.fn()}
        onCancel={onCancel}
      />
    );

    expect(screen.getByRole('dialog', { name: /add new block/i })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});
