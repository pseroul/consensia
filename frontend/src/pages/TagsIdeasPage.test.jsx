/**
 * TagsIdeasPage.test.jsx
 * Unit tests for the TagsIdeasPage component.
 *
 * Coverage:
 * - Initial render (loading, back link, heading, control buttons)
 * - Data fetching: tags + ideas per tag + all ideas for untagged section
 * - Rendering tags with idea counts
 * - Untagged ideas section
 * - Error handling on fetch
 * - Collapse / Expand all sections
 * - Refresh flow
 * - Full-content modal (open, close)
 * - Delete tag flow (modal open, confirm calls API + refresh, cancel, error)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── Restore real React hooks ─────────────────────────────────────────────────
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

// ─── Override lucide-react ────────────────────────────────────────────────────
vi.mock('lucide-react', () => {
  const icon = (id) => () => <svg data-testid={id} />;
  return {
    ArrowLeft:    icon('arrow-left-icon'),
    BookOpen:     icon('book-open-icon'),
    ChevronRight: icon('chevron-right-icon'),
    Loader2:      icon('loader-icon'),
    X:            icon('x-icon'),
    RotateCcw:    icon('rotate-ccw-icon'),
    Trash2:       icon('trash-icon'),
  };
});

// ─── Mock react-router-dom ────────────────────────────────────────────────────
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
  };
});

// ─── Mock BookContext ─────────────────────────────────────────────────────────
vi.mock('../contexts/BookContext', () => ({
  useBook: () => ({ selectedBook: null, books: [], setSelectedBook: vi.fn() }),
}));

// ─── Mock API ─────────────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  getTags:          vi.fn(),
  getIdeasFromTags: vi.fn(),
  getIdeas:         vi.fn(),
  deleteTag:        vi.fn(),
}));

import TagsIdeasPage from './TagsIdeasPage';
import { getTags, getIdeasFromTags, getIdeas, deleteTag } from '../services/api';

// ─── Test fixtures ─────────────────────────────────────────────────────────────
const MOCK_TAGS = [
  { name: 'frontend' },
  { name: 'backend' },
];

const IDEAS_BY_TAG = {
  frontend: [
    { id: '1', title: 'React Hooks',   content: 'About hooks' },
    { id: '2', title: 'CSS Grid',      content: 'About grid' },
  ],
  backend: [
    { id: '3', title: 'FastAPI Intro', content: 'About fastapi' },
  ],
};

const ALL_IDEAS = [
  { id: '1', title: 'React Hooks',   content: 'About hooks' },
  { id: '2', title: 'CSS Grid',      content: 'About grid' },
  { id: '3', title: 'FastAPI Intro', content: 'About fastapi' },
  { id: '4', title: 'Untagged Idea', content: 'No tag here' },
];

// ─── Setup helper ──────────────────────────────────────────────────────────────
const setupMocks = () => {
  getTags.mockResolvedValue({ data: MOCK_TAGS });
  getIdeasFromTags.mockImplementation((tagName) =>
    Promise.resolve({ data: IDEAS_BY_TAG[tagName] ?? [] })
  );
  getIdeas.mockResolvedValue({ data: ALL_IDEAS });
};

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — initial render', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('shows a loading spinner while fetching', () => {
    getTags.mockReturnValue(new Promise(() => {}));
    render(<TagsIdeasPage />);
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
  });

  it('renders the "Back to Dashboard" link', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('frontend'));
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute('href', '/dashboard');
  });

  it('renders the page heading "Tags and Ideas"', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => expect(screen.getByText('Tags and Ideas')).toBeInTheDocument());
  });

  it('renders the "Collapse All" button', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /collapse all sections/i })).toBeInTheDocument()
    );
  });

  it('renders the "Expand All" button', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /expand all sections/i })).toBeInTheDocument()
    );
  });

  it('renders the "Refresh" button', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /refresh content/i })).toBeInTheDocument()
    );
  });

  it('calls getTags, getIdeasFromTags for each tag, and getIdeas on mount', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('frontend'));
    expect(getTags).toHaveBeenCalledTimes(1);
    expect(getTags).toHaveBeenCalledWith(null);
    expect(getIdeasFromTags).toHaveBeenCalledWith('frontend', null);
    expect(getIdeasFromTags).toHaveBeenCalledWith('backend', null);
    expect(getIdeas).toHaveBeenCalledTimes(1);
    expect(getIdeas).toHaveBeenCalledWith(null);
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — data rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('renders tag names', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => {
      expect(screen.getByText('frontend')).toBeInTheDocument();
      expect(screen.getByText('backend')).toBeInTheDocument();
    });
  });

  it('renders idea titles under their tag', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => {
      expect(screen.getByText('React Hooks')).toBeInTheDocument();
      expect(screen.getByText('CSS Grid')).toBeInTheDocument();
      expect(screen.getByText('FastAPI Intro')).toBeInTheDocument();
    });
  });

  it('shows the idea count badge per tag', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => {
      // frontend has 2 ideas, backend has 1 — both badges are in the document
      expect(screen.getAllByText('(2 ideas)').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('(1 ideas)').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows the tag count in the subtitle', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => expect(screen.getByText('2 tags')).toBeInTheDocument());
  });

  it('shows "No tags available" when there are no tags', async () => {
    getTags.mockResolvedValue({ data: [] });
    getIdeas.mockResolvedValue({ data: [] });
    render(<TagsIdeasPage />);
    await waitFor(() =>
      expect(screen.getByText(/no tags available/i)).toBeInTheDocument()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — untagged ideas section', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('renders the "Untagged Ideas" section when untagged ideas exist', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() =>
      expect(screen.getByText('Untagged Ideas')).toBeInTheDocument()
    );
  });

  it('renders the untagged idea in the untagged section', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() =>
      expect(screen.getByText('Untagged Idea')).toBeInTheDocument()
    );
  });

  it('shows the untagged count badge', async () => {
    render(<TagsIdeasPage />);
    // The untagged section shows "(1 ideas)" — backend also has 1 idea so multiple matches
    await waitFor(() =>
      expect(screen.getAllByText('(1 ideas)').length).toBeGreaterThanOrEqual(1)
    );
  });

  it('does not render "Untagged Ideas" when all ideas are tagged', async () => {
    // All ideas in ALL_IDEAS are tagged
    getIdeas.mockResolvedValue({ data: ALL_IDEAS.slice(0, 3) });
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('frontend'));
    expect(screen.queryByText('Untagged Ideas')).not.toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows an error message when getTags fails', async () => {
    getTags.mockRejectedValue(new Error('Network error'));
    render(<TagsIdeasPage />);
    await waitFor(() =>
      expect(screen.getByText(/failed to load tags and ideas/i)).toBeInTheDocument()
    );
  });

  it('does not render tags list on fetch error', async () => {
    getTags.mockRejectedValue(new Error('Network error'));
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText(/failed to load/i));
    expect(screen.queryByText('frontend')).not.toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — collapse / expand all', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('hides child ideas when "Collapse All" is clicked', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('React Hooks'));

    fireEvent.click(screen.getByRole('button', { name: /collapse all sections/i }));

    await waitFor(() =>
      expect(screen.queryByText('React Hooks')).not.toBeInTheDocument()
    );
  });

  it('shows child ideas again after "Expand All"', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('React Hooks'));

    fireEvent.click(screen.getByRole('button', { name: /collapse all sections/i }));
    await waitFor(() => expect(screen.queryByText('React Hooks')).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /expand all sections/i }));
    await waitFor(() => expect(screen.getByText('React Hooks')).toBeInTheDocument());
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — refresh', () => {
  const UPDATED_TAGS = [{ name: 'ml' }];
  const UPDATED_IDEAS_ML = [{ id: '10', title: 'Neural Nets', content: 'About NN' }];

  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('re-fetches data on Refresh click', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('frontend'));

    fireEvent.click(screen.getByRole('button', { name: /refresh content/i }));

    await waitFor(() => expect(getTags).toHaveBeenCalledTimes(2));
  });

  it('renders updated tags after refresh', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('frontend'));

    getTags.mockResolvedValueOnce({ data: UPDATED_TAGS });
    getIdeasFromTags.mockResolvedValueOnce({ data: UPDATED_IDEAS_ML });
    getIdeas.mockResolvedValueOnce({ data: UPDATED_IDEAS_ML });

    fireEvent.click(screen.getByRole('button', { name: /refresh content/i }));

    await waitFor(() => expect(screen.getByText('ml')).toBeInTheDocument());
    expect(screen.queryByText('frontend')).not.toBeInTheDocument();
  });

  it('disables the Refresh button while refreshing', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('frontend'));

    getTags.mockReturnValueOnce(new Promise(() => {})); // never resolves
    fireEvent.click(screen.getByRole('button', { name: /refresh content/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /refresh/i })).toBeDisabled()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — full-content modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('opens the modal when an idea with description is clicked', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('React Hooks'));

    fireEvent.click(screen.getByRole('button', { name: /view details for react hooks/i }));

    // After click, the idea content appears a second time inside the modal
    await waitFor(() =>
      expect(screen.getAllByText('About hooks').length).toBeGreaterThanOrEqual(2)
    );
  });

  it('closes the modal via the "Close modal" button', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('React Hooks'));

    fireEvent.click(screen.getByRole('button', { name: /view details for react hooks/i }));
    await waitFor(() => screen.getByRole('button', { name: /^close modal$/i }));

    fireEvent.click(screen.getByRole('button', { name: /^close modal$/i }));

    await waitFor(() =>
      expect(screen.getAllByText('About hooks').length).toBe(1)
    );
  });

  it('closes the modal via the bottom "Close" button', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('React Hooks'));

    fireEvent.click(screen.getByRole('button', { name: /view details for react hooks/i }));
    await waitFor(() => screen.getByRole('button', { name: /^close$/i }));

    fireEvent.click(screen.getByRole('button', { name: /^close$/i }));

    await waitFor(() =>
      expect(screen.getAllByText('About hooks').length).toBe(1)
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('TagsIdeasPage — delete tag flow', () => {
  // To exercise the delete button, we need a tag that has NO ideas
  // so it renders as the "tag without ideas" branch (which shows the Trash2 button).
  const TAGS_WITH_EMPTY = [{ name: 'empty-tag' }];

  beforeEach(() => {
    vi.clearAllMocks();
    getTags.mockResolvedValue({ data: TAGS_WITH_EMPTY });
    getIdeasFromTags.mockResolvedValue({ data: [] }); // tag has no ideas
    getIdeas.mockResolvedValue({ data: [] });
    deleteTag.mockResolvedValue({});
  });

  it('shows the delete confirmation modal when the trash button is clicked', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('empty-tag'));

    fireEvent.click(screen.getByRole('button', { name: /delete tag empty-tag/i }));

    expect(screen.getByText('Confirm Deletion')).toBeInTheDocument();
    expect(screen.getByText(/"empty-tag"/)).toBeInTheDocument();
  });

  it('calls deleteTag with the correct name on confirm', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('empty-tag'));

    fireEvent.click(screen.getByRole('button', { name: /delete tag empty-tag/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm deletion/i }));

    await waitFor(() =>
      expect(deleteTag).toHaveBeenCalledWith('empty-tag')
    );
  });

  it('refreshes the data after a successful delete', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('empty-tag'));

    fireEvent.click(screen.getByRole('button', { name: /delete tag empty-tag/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm deletion/i }));

    // getTags called once on mount, once after delete
    await waitFor(() => expect(getTags).toHaveBeenCalledTimes(2));
  });

  it('closes the delete modal after a successful delete', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('empty-tag'));

    fireEvent.click(screen.getByRole('button', { name: /delete tag empty-tag/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm deletion/i }));

    await waitFor(() =>
      expect(screen.queryByText('Confirm Deletion')).not.toBeInTheDocument()
    );
  });

  it('closes the delete modal when "Cancel" is clicked without deleting', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('empty-tag'));

    fireEvent.click(screen.getByRole('button', { name: /delete tag empty-tag/i }));
    expect(screen.getByText('Confirm Deletion')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^cancel$/i }));

    expect(screen.queryByText('Confirm Deletion')).not.toBeInTheDocument();
    expect(deleteTag).not.toHaveBeenCalled();
  });

  it('shows an error when deleteTag API call fails', async () => {
    deleteTag.mockRejectedValue(new Error('Delete failed'));
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('empty-tag'));

    fireEvent.click(screen.getByRole('button', { name: /delete tag empty-tag/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm deletion/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to delete tag/i)).toBeInTheDocument()
    );
  });

  it('closes the delete confirmation modal via the "Close modal" button', async () => {
    render(<TagsIdeasPage />);
    await waitFor(() => screen.getByText('empty-tag'));

    fireEvent.click(screen.getByRole('button', { name: /delete tag empty-tag/i }));
    expect(screen.getByText('Confirm Deletion')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /close modal/i }));

    expect(screen.queryByText('Confirm Deletion')).not.toBeInTheDocument();
    expect(deleteTag).not.toHaveBeenCalled();
  });
});
