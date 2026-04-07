/**
 * Dashboard.test.jsx
 * Unit tests for the Dashboard page component.
 *
 * Strategy:
 * - Mock all API calls from ../services/api
 * - Mock IdeaModal to isolate Dashboard logic
 * - Use real React hooks (override the global setupTests mock)
 * - Cover: rendering, loading state, search/filter, similar ideas, CRUD actions
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── Override the global React mock from setupTests.js ────────────────────────
// setupTests mocks React hooks globally, which prevents components from working.
// We restore the real implementation for this test file.
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

// ─── Override the global lucide-react mock (adds icons missing from setupTests) ─
vi.mock('lucide-react', () => {
  const icon = (testId) => () => <svg data-testid={testId} />;
  return {
    Plus:     icon('plus-icon'),
    Search:   icon('search-icon'),
    Trash2:   icon('trash-icon'),
    Edit3:    icon('edit3-icon'),
    Loader2:  icon('loader-icon'),
    Lightbulb: icon('lightbulb-icon'),
    X:        icon('x-icon'),
    Tag:      icon('tag-icon'),
  };
});

// ─── Mock BookContext ─────────────────────────────────────────────────────────
let mockSelectedBook = null;
vi.mock('../contexts/BookContext', () => ({
  useBook: () => ({ selectedBook: mockSelectedBook, books: [], setSelectedBook: vi.fn() }),
}));

// ─── Mock API services ────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  getIdeas: vi.fn(),
  getUserIdeas: vi.fn(),
  createIdea: vi.fn(),
  updateIdea: vi.fn(),
  deleteIdea: vi.fn(),
  getSimilarIdeas: vi.fn(),
}));

// ─── Mock VoteButtons to isolate Dashboard logic ──────────────────────────────
vi.mock('../components/VoteButtons', () => ({
  default: ({ ideaId }) => <div data-testid={`vote-buttons-${ideaId}`} />,
}));

// ─── Mock IdeaModal to isolate Dashboard logic ────────────────────────────────
vi.mock('../components/IdeaModal', () => ({
  default: ({ isOpen, onClose, onSave, initialData }) => {
    if (!isOpen) return null;
    return (
      <div data-testid="idea-modal">
        <span data-testid="modal-mode">{initialData ? 'edit' : 'create'}</span>
        <button onClick={onClose} data-testid="modal-close">Close</button>
        <button
          onClick={() => onSave({ title: 'Saved Idea', content: 'Saved Content', tags: '' })}
          data-testid="modal-save"
        >
          Save
        </button>
      </div>
    );
  },
}));

import Dashboard from './Dashboard';
import { getIdeas, getUserIdeas, createIdea, updateIdea, deleteIdea, getSimilarIdeas } from '../services/api';

// ─── Test fixtures ─────────────────────────────────────────────────────────────
const MOCK_IDEAS = [
  { id: '1', title: 'Idea Alpha', content: 'Content for alpha', tags: 'tech;ai',      book_id: 1 },
  { id: '2', title: 'Idea Beta',  content: 'Content for beta',  tags: 'science',      book_id: 1 },
  { id: '3', title: 'Idea Gamma', content: 'Content about tech', tags: '',            book_id: 1 },
];

const MOCK_SIMILAR = [
  { id: '4', title: 'Similar One', content: 'Similar content', tags: 'ml', book_id: 1 },
];

// ─── Helpers ───────────────────────────────────────────────────────────────────
const renderDashboard = () => render(<Dashboard />);

const resolvedGetIdeas = (ideas = MOCK_IDEAS) =>
  getIdeas.mockResolvedValue({ data: ideas });

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — initial render', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resolvedGetIdeas();
  });

  it('shows a loading spinner while fetching ideas', () => {
    // getIdeas never resolves during this tick — component stays in loading state
    getIdeas.mockReturnValue(new Promise(() => {}));
    renderDashboard();
    // The big page Loader2 icon is rendered while isLoading=true (mocked as loader-icon)
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
    // Ideas grid is not yet visible
    expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
  });

  it('renders the page title "Ideas"', async () => {
    renderDashboard();
    await waitFor(() => expect(screen.getByText('Ideas')).toBeInTheDocument());
  });

  it('renders the search input', async () => {
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByPlaceholderText('Search...')).toBeInTheDocument()
    );
  });

  it('renders the "New" button', async () => {
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /new/i })).toBeInTheDocument()
    );
  });

  it('renders the "Similar" button disabled when search is empty', async () => {
    renderDashboard();
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /similar/i });
      expect(btn).toBeDisabled();
    });
  });

  it('displays all fetched ideas after loading', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('Idea Alpha')).toBeInTheDocument();
      expect(screen.getByText('Idea Beta')).toBeInTheDocument();
      expect(screen.getByText('Idea Gamma')).toBeInTheDocument();
    });
  });

  it('displays idea content text', async () => {
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('Content for alpha')).toBeInTheDocument()
    );
  });

  it('calls getIdeas exactly once on mount', async () => {
    renderDashboard();
    await waitFor(() => expect(getIdeas).toHaveBeenCalledTimes(1));
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — tag rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resolvedGetIdeas();
  });

  it('renders tags split by semicolon as individual pills', async () => {
    renderDashboard();
    await waitFor(() => {
      expect(screen.getByText('tech')).toBeInTheDocument();
      expect(screen.getByText('ai')).toBeInTheDocument();
      expect(screen.getByText('science')).toBeInTheDocument();
    });
  });

  it('does not render a tags section when tags field is empty', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Gamma'));
    // "TAGS:" label should appear only twice (for Alpha and Beta)
    const tagLabels = screen.getAllByText('TAGS:');
    expect(tagLabels).toHaveLength(2);
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — local search filtering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resolvedGetIdeas();
  });

  it('filters ideas by title', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'alpha' },
    });

    expect(screen.getByText('Idea Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Idea Beta')).not.toBeInTheDocument();
    expect(screen.queryByText('Idea Gamma')).not.toBeInTheDocument();
  });

  it('filters ideas by content', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Beta'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'beta' },
    });

    expect(screen.getByText('Idea Beta')).toBeInTheDocument();
    expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
  });

  it('filters ideas by tag', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'science' },
    });

    expect(screen.getByText('Idea Beta')).toBeInTheDocument();
    expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
  });

  it('shows all ideas when search is cleared', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const input = screen.getByPlaceholderText('Search...');
    fireEvent.change(input, { target: { value: 'alpha' } });
    fireEvent.change(input, { target: { value: '' } });

    expect(screen.getByText('Idea Alpha')).toBeInTheDocument();
    expect(screen.getByText('Idea Beta')).toBeInTheDocument();
    expect(screen.getByText('Idea Gamma')).toBeInTheDocument();
  });

  it('is case-insensitive', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'ALPHA' },
    });

    expect(screen.getByText('Idea Alpha')).toBeInTheDocument();
    expect(screen.queryByText('Idea Beta')).not.toBeInTheDocument();
  });

  it('enables the Similar button when search is not empty', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'alpha' },
    });

    expect(screen.getByRole('button', { name: /similar/i })).not.toBeDisabled();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — similar ideas search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resolvedGetIdeas();
    getSimilarIdeas.mockResolvedValue({ data: MOCK_SIMILAR });
  });

  it('calls getSimilarIdeas with the current search term on button click', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'tech' },
    });
    fireEvent.click(screen.getByRole('button', { name: /similar/i }));

    await waitFor(() =>
      expect(getSimilarIdeas).toHaveBeenCalledWith('tech')
    );
  });

  it('replaces the grid with similar results after search', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'tech' },
    });
    fireEvent.click(screen.getByRole('button', { name: /similar/i }));

    await waitFor(() => {
      expect(screen.getByText('Similar One')).toBeInTheDocument();
      expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
    });
  });

  it('resets similar results when typing in the search box', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'tech' },
    });
    fireEvent.click(screen.getByRole('button', { name: /similar/i }));
    await waitFor(() => screen.getByText('Similar One'));

    // Now type again — similar results should be dismissed, regular filter kicks in
    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'alpha' },
    });

    await waitFor(() => {
      expect(screen.queryByText('Similar One')).not.toBeInTheDocument();
      expect(screen.getByText('Idea Alpha')).toBeInTheDocument();
    });
  });

  it('shows an empty grid when similar search returns no results', async () => {
    getSimilarIdeas.mockResolvedValue({ data: [] });
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'xyz' },
    });
    fireEvent.click(screen.getByRole('button', { name: /similar/i }));

    await waitFor(() => {
      expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
      expect(screen.queryByText('Similar One')).not.toBeInTheDocument();
    });
  });

  it('does not call getSimilarIdeas when search term is blank', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    // Button is disabled, but test the guard too
    await expect(getSimilarIdeas).not.toHaveBeenCalled();
  });

  it('handles getSimilarIdeas API error gracefully', async () => {
    getSimilarIdeas.mockRejectedValue(new Error('Network error'));
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.change(screen.getByPlaceholderText('Search...'), {
      target: { value: 'tech' },
    });
    fireEvent.click(screen.getByRole('button', { name: /similar/i }));

    // Grid should show empty (showSimilarResults=true, similarIdeas=[])
    await waitFor(() => {
      expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — create idea modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSelectedBook = { id: 1, title: 'Test Book' };
    resolvedGetIdeas();
    createIdea.mockResolvedValue({ data: { id: '99' } });
  });

  it('opens the modal in create mode when "New" is clicked', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /new/i }));

    expect(screen.getByTestId('idea-modal')).toBeInTheDocument();
    expect(screen.getByTestId('modal-mode')).toHaveTextContent('create');
  });

  it('closes the modal when IdeaModal calls onClose', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /new/i }));
    expect(screen.getByTestId('idea-modal')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('modal-close'));
    expect(screen.queryByTestId('idea-modal')).not.toBeInTheDocument();
  });

  it('calls createIdea and refreshes the list on save', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /new/i }));
    fireEvent.click(screen.getByTestId('modal-save'));

    await waitFor(() => {
      expect(createIdea).toHaveBeenCalledTimes(1);
      expect(createIdea).toHaveBeenCalledWith({
        title: 'Saved Idea',
        content: 'Saved Content',
        tags: '',
      });
      // getIdeas is called once on mount + once after save
      expect(getIdeas).toHaveBeenCalledTimes(2);
    });
  });

  it('closes the modal after a successful save', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /new/i }));
    fireEvent.click(screen.getByTestId('modal-save'));

    await waitFor(() =>
      expect(screen.queryByTestId('idea-modal')).not.toBeInTheDocument()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — edit idea modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSelectedBook = { id: 1, title: 'Test Book' };
    resolvedGetIdeas();
    updateIdea.mockResolvedValue({ data: {} });
  });

  it('opens the modal in edit mode when the edit button is clicked', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const editButtons = screen.getAllByRole('button', { name: /edit idea/i });
    fireEvent.click(editButtons[0]);

    expect(screen.getByTestId('idea-modal')).toBeInTheDocument();
    expect(screen.getByTestId('modal-mode')).toHaveTextContent('edit');
  });

  it('calls updateIdea with the correct id on save', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const editButtons = screen.getAllByRole('button', { name: /edit idea/i });
    fireEvent.click(editButtons[0]); // Edits MOCK_IDEAS[0] — id '1'

    fireEvent.click(screen.getByTestId('modal-save'));

    await waitFor(() => {
      expect(updateIdea).toHaveBeenCalledTimes(1);
      expect(updateIdea).toHaveBeenCalledWith('1', {
        title: 'Saved Idea',
        content: 'Saved Content',
        tags: '',
      });
    });
  });

  it('refreshes the list after a successful edit', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const editButtons = screen.getAllByRole('button', { name: /edit idea/i });
    fireEvent.click(editButtons[0]);
    fireEvent.click(screen.getByTestId('modal-save'));

    await waitFor(() => expect(getIdeas).toHaveBeenCalledTimes(2));
  });

  it('resets editingIdea to null after modal is closed without saving', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const editButtons = screen.getAllByRole('button', { name: /edit idea/i });
    fireEvent.click(editButtons[0]);
    fireEvent.click(screen.getByTestId('modal-close'));

    // Reopen — should now be in create mode
    fireEvent.click(screen.getByRole('button', { name: /new/i }));
    expect(screen.getByTestId('modal-mode')).toHaveTextContent('create');
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — delete idea', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resolvedGetIdeas();
    deleteIdea.mockResolvedValue({});
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('calls window.confirm before deleting', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const deleteButtons = screen.getAllByRole('button', { name: /delete idea/i });
    fireEvent.click(deleteButtons[0]);

    expect(window.confirm).toHaveBeenCalledWith('Delete this idea?');
  });

  it('calls deleteIdea with the correct id when confirmed', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const deleteButtons = screen.getAllByRole('button', { name: /delete idea/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => {
      expect(deleteIdea).toHaveBeenCalledTimes(1);
      expect(deleteIdea).toHaveBeenCalledWith('1', MOCK_IDEAS[0]);
    });
  });

  it('refreshes the list after a successful delete', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const deleteButtons = screen.getAllByRole('button', { name: /delete idea/i });
    fireEvent.click(deleteButtons[0]);

    await waitFor(() => expect(getIdeas).toHaveBeenCalledTimes(2));
  });

  it('does NOT call deleteIdea when the user cancels the confirmation', async () => {
    window.confirm.mockReturnValue(false);
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const deleteButtons = screen.getAllByRole('button', { name: /delete idea/i });
    fireEvent.click(deleteButtons[0]);

    expect(deleteIdea).not.toHaveBeenCalled();
  });

  it('handles deleteIdea API error gracefully without crashing', async () => {
    deleteIdea.mockRejectedValue(new Error('Server error'));
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    const deleteButtons = screen.getAllByRole('button', { name: /delete idea/i });
    fireEvent.click(deleteButtons[0]);

    // Should not throw — component stays rendered
    await waitFor(() =>
      expect(screen.getByText('Idea Alpha')).toBeInTheDocument()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — save idea error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSelectedBook = { id: 1, title: 'Test Book' };
    resolvedGetIdeas();
    vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  it('shows an alert with error details when createIdea fails with a 422', async () => {
    createIdea.mockRejectedValue({
      response: { data: { detail: [{ msg: 'field required', loc: ['title'] }] } },
    });

    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /new/i }));
    fireEvent.click(screen.getByTestId('modal-save'));

    await waitFor(() => expect(window.alert).toHaveBeenCalledTimes(1));
    expect(window.alert).toHaveBeenCalledWith(expect.stringContaining('422'));
  });

  it('keeps the modal open after a save error', async () => {
    createIdea.mockRejectedValue({
      response: { data: { detail: 'Unprocessable' } },
    });

    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /new/i }));
    fireEvent.click(screen.getByTestId('modal-save'));

    await waitFor(() => window.alert.mock.calls.length > 0);
    // Modal stays open because onSave threw
    expect(screen.getByTestId('idea-modal')).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — getFilteredIdeas pure logic', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSelectedBook = null;
    resolvedGetIdeas();
  });

  it('gracefully handles ideas where title is null/undefined', async () => {
    getIdeas.mockResolvedValue({
      data: [{ id: '10', title: null, content: 'No title here', tags: '' }],
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No title here')).toBeInTheDocument()
    );
  });

  it('gracefully handles ideas where content is null/undefined', async () => {
    getIdeas.mockResolvedValue({
      data: [{ id: '11', title: 'No content idea', content: null, tags: '' }],
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No content idea')).toBeInTheDocument()
    );
  });

  it('gracefully handles ideas where tags is null/undefined', async () => {
    getIdeas.mockResolvedValue({
      data: [{ id: '12', title: 'No tags idea', content: 'Content', tags: null }],
    });
    renderDashboard();
    await waitFor(() =>
      expect(screen.getByText('No tags idea')).toBeInTheDocument()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Dashboard — radio button filtering', () => {
  const MOCK_USER_IDEAS = [
    { id: '1', title: 'My Idea One', content: 'My first idea', tags: 'personal' },
    { id: '2', title: 'My Idea Two', content: 'My second idea', tags: 'work' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockSelectedBook = null;
    resolvedGetIdeas();
    getUserIdeas.mockResolvedValue({ data: MOCK_USER_IDEAS });
  });

  it('renders radio buttons for filtering ideas', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    expect(screen.getByLabelText('All Ideas')).toBeInTheDocument();
    expect(screen.getByLabelText('My Ideas')).toBeInTheDocument();
  });

  it('defaults to showing all ideas (All Ideas radio selected)', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    expect(screen.getByText('Idea Alpha')).toBeInTheDocument();
    expect(screen.getByText('Idea Beta')).toBeInTheDocument();
    expect(screen.getByText('Idea Gamma')).toBeInTheDocument();
    expect(screen.queryByText('My Idea One')).not.toBeInTheDocument();
  });

  it('calls getUserIdeas when My Ideas radio is selected', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByLabelText('My Ideas'));

    await waitFor(() => {
      expect(getUserIdeas).toHaveBeenCalledTimes(1);
      expect(getIdeas).toHaveBeenCalledTimes(1); // Initial call
    });
  });

  it('displays user ideas when My Ideas radio is selected', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByLabelText('My Ideas'));

    await waitFor(() => {
      expect(screen.getByText('My Idea One')).toBeInTheDocument();
      expect(screen.getByText('My Idea Two')).toBeInTheDocument();
      expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
      expect(screen.queryByText('Idea Beta')).not.toBeInTheDocument();
    });
  });

  it('calls getIdeas when All Ideas radio is selected', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    // First select My Ideas
    fireEvent.click(screen.getByLabelText('My Ideas'));
    await waitFor(() => screen.getByText('My Idea One'));

    // Then select All Ideas again
    fireEvent.click(screen.getByLabelText('All Ideas'));

    await waitFor(() => {
      expect(getIdeas).toHaveBeenCalledTimes(2); // Initial + after switching back
      expect(getUserIdeas).toHaveBeenCalledTimes(1); // Only when My Ideas was selected
    });
  });

  it('displays all ideas when All Ideas radio is selected after My Ideas', async () => {
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    // First select My Ideas
    fireEvent.click(screen.getByLabelText('My Ideas'));
    await waitFor(() => screen.getByText('My Idea One'));

    // Then select All Ideas again
    fireEvent.click(screen.getByLabelText('All Ideas'));

    await waitFor(() => {
      expect(screen.getByText('Idea Alpha')).toBeInTheDocument();
      expect(screen.getByText('Idea Beta')).toBeInTheDocument();
      expect(screen.getByText('Idea Gamma')).toBeInTheDocument();
      expect(screen.queryByText('My Idea One')).not.toBeInTheDocument();
    });
  });

  it('handles getUserIdeas API error gracefully', async () => {
    getUserIdeas.mockRejectedValue(new Error('Network error'));
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByLabelText('My Ideas'));

    // Should not crash and should still show loading state
    await waitFor(() => {
      expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
    });
  });

  it('handles empty user ideas array', async () => {
    getUserIdeas.mockResolvedValue({ data: [] });
    renderDashboard();
    await waitFor(() => screen.getByText('Idea Alpha'));

    fireEvent.click(screen.getByLabelText('My Ideas'));

    await waitFor(() => {
      expect(screen.queryByText('Idea Alpha')).not.toBeInTheDocument();
      expect(screen.queryByText('My Idea One')).not.toBeInTheDocument();
    });
  });
});
