/**
 * TableOfContents.test.jsx
 * Unit tests for the TableOfContents page component.
 *
 * Coverage:
 * - Initial render (loading, back link, heading, control buttons)
 * - Data fetching on mount and error states
 * - Rendering TOC structure (headings, idea items, item counts)
 * - Collapse / Expand all sections
 * - Refresh flow (updateTocStructure + getTocStructure called, errors handled)
 * - Full-content modal (open on idea click, close button, close on button)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── Restore real React hooks ─────────────────────────────────────────────────
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

// ─── Override lucide-react (adds all icons used by this component) ────────────
vi.mock('lucide-react', () => {
  const icon = (id) => () => <svg data-testid={id} />;
  return {
    ArrowLeft:  icon('arrow-left-icon'),
    BookOpen:   icon('book-open-icon'),
    ChevronRight: icon('chevron-right-icon'),
    Download:   icon('download-icon'),
    Loader2:    icon('loader-icon'),
    X:          icon('x-icon'),
    RotateCcw:  icon('rotate-ccw-icon'),
  };
});

// ─── Mock react-router-dom (Link rendered as <a>) ─────────────────────────────
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
  };
});

// ─── Mock BookContext ─────────────────────────────────────────────────────────
vi.mock('../contexts/BookContext', () => ({
  useBook: vi.fn(() => ({ selectedBook: null, books: [], setSelectedBook: vi.fn() })),
}));

// ─── Mock API ─────────────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  getTocStructure:        vi.fn(),
  updateTocStructure:     vi.fn(),
  getIdeas:               vi.fn(),
  getBookImpactComments:  vi.fn(),
}));

import TableOfContents from './TableOfContents';
import { getTocStructure, updateTocStructure, getIdeas, getBookImpactComments } from '../services/api';
import { useBook } from '../contexts/BookContext';

// ─── Test fixtures ─────────────────────────────────────────────────────────────
const MOCK_TOC = [
  {
    id: 'h1',
    type: 'heading',
    title: 'Chapter One',
    originality: '0.9',
    children: [
      { id: 'i1', type: 'idea', title: 'First Idea',  text: 'Content of first idea',  originality: '0.8' },
      { id: 'i2', type: 'idea', title: 'Second Idea', text: 'Content of second idea', originality: '0.7' },
    ],
  },
  {
    id: 'h2',
    type: 'heading',
    title: 'Chapter Two',
    originality: '0.6',
    children: [],
  },
];

const MOCK_IDEAS = [
  { id: 1, title: 'First Idea',  content: 'Content of first idea',  book_id: 1, score: 4,  tags: 'ai;hardware' },
  { id: 2, title: 'Second Idea', content: 'Content of second idea', book_id: 1, score: -2, tags: null },
];

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — initial render', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTocStructure.mockResolvedValue({ data: MOCK_TOC });
    getIdeas.mockResolvedValue({ data: MOCK_IDEAS });
  });

  it('shows a loading spinner while fetching', () => {
    getTocStructure.mockReturnValue(new Promise(() => {}));
    render(<TableOfContents />);
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
  });

  it('renders the "Back to Dashboard" link', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));
    expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute('href', '/dashboard');
  });

  it('renders the page heading "Table of contents"', async () => {
    render(<TableOfContents />);
    await waitFor(() => expect(screen.getByText('Table of contents')).toBeInTheDocument());
  });

  it('renders the "Collapse All" button', async () => {
    render(<TableOfContents />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /collapse all sections/i })).toBeInTheDocument()
    );
  });

  it('renders the "Expand All" button', async () => {
    render(<TableOfContents />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /expand all sections/i })).toBeInTheDocument()
    );
  });

  it('renders the "Refresh" button', async () => {
    render(<TableOfContents />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /refresh content/i })).toBeInTheDocument()
    );
  });

  it('calls getTocStructure once on mount', async () => {
    render(<TableOfContents />);
    await waitFor(() => expect(getTocStructure).toHaveBeenCalledTimes(1));
  });
});

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — data rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTocStructure.mockResolvedValue({ data: MOCK_TOC });
    getIdeas.mockResolvedValue({ data: MOCK_IDEAS });
  });

  it('renders top-level heading titles', async () => {
    render(<TableOfContents />);
    await waitFor(() => {
      expect(screen.getByText('Chapter One')).toBeInTheDocument();
      expect(screen.getByText('Chapter Two')).toBeInTheDocument();
    });
  });

  it('renders child idea titles under a heading', async () => {
    render(<TableOfContents />);
    await waitFor(() => {
      expect(screen.getByText('First Idea')).toBeInTheDocument();
      expect(screen.getByText('Second Idea')).toBeInTheDocument();
    });
  });

  it('shows the child item count badge on headings with children', async () => {
    render(<TableOfContents />);
    await waitFor(() => expect(screen.getByText('(2 items)')).toBeInTheDocument());
  });

  it('shows "No content available" when TOC is empty', async () => {
    getTocStructure.mockResolvedValue({ data: [] });
    render(<TableOfContents />);
    await waitFor(() =>
      expect(screen.getByText(/no content available/i)).toBeInTheDocument()
    );
  });

  it('shows the popularity score badge for each leaf idea', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('First Idea'));
    const badges = screen.getAllByTestId('popularity-score');
    expect(badges.length).toBeGreaterThan(0);
    // First Idea has score 4 → displayed as "+4"
    expect(screen.getByText('+4')).toBeInTheDocument();
    // Second Idea has score -2 → displayed as "-2"
    expect(screen.getByText('-2')).toBeInTheDocument();
  });

  it('shows the section count in the subtitle', async () => {
    render(<TableOfContents />);
    await waitFor(() => expect(screen.getByText('2 sections')).toBeInTheDocument());
  });
});

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getIdeas.mockResolvedValue({ data: MOCK_IDEAS });
  });

  it('shows an error message when getTocStructure fails', async () => {
    getTocStructure.mockRejectedValue(new Error('Network error'));
    render(<TableOfContents />);
    await waitFor(() =>
      expect(screen.getByText(/failed to load table of contents/i)).toBeInTheDocument()
    );
  });

  it('does not render the heading list on fetch error', async () => {
    getTocStructure.mockRejectedValue(new Error('Network error'));
    render(<TableOfContents />);
    await waitFor(() => screen.getByText(/failed to load/i));
    expect(screen.queryByText('Chapter One')).not.toBeInTheDocument();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — collapse / expand all', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTocStructure.mockResolvedValue({ data: MOCK_TOC });
    getIdeas.mockResolvedValue({ data: MOCK_IDEAS });
  });

  it('hides child ideas when "Collapse All" is clicked', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('First Idea'));

    fireEvent.click(screen.getByRole('button', { name: /collapse all sections/i }));

    await waitFor(() =>
      expect(screen.queryByText('First Idea')).not.toBeInTheDocument()
    );
  });

  it('shows child ideas again when "Expand All" is clicked after collapsing', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('First Idea'));

    fireEvent.click(screen.getByRole('button', { name: /collapse all sections/i }));
    await waitFor(() => expect(screen.queryByText('First Idea')).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /expand all sections/i }));
    await waitFor(() => expect(screen.getByText('First Idea')).toBeInTheDocument());
  });
});

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — refresh', () => {
  const UPDATED_TOC = [
    { id: 'h3', type: 'heading', title: 'New Chapter', originality: '0.5', children: [] },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    getTocStructure.mockResolvedValue({ data: MOCK_TOC });
    updateTocStructure.mockResolvedValue({});
    getIdeas.mockResolvedValue({ data: MOCK_IDEAS });
  });

  it('calls updateTocStructure then getTocStructure on Refresh click', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    getTocStructure.mockResolvedValueOnce({ data: UPDATED_TOC });
    fireEvent.click(screen.getByRole('button', { name: /refresh content/i }));

    await waitFor(() => {
      expect(updateTocStructure).toHaveBeenCalledTimes(1);
      expect(getTocStructure).toHaveBeenCalledTimes(2);
    });
  });

  it('renders updated content after refresh', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    getTocStructure.mockResolvedValueOnce({ data: UPDATED_TOC });
    fireEvent.click(screen.getByRole('button', { name: /refresh content/i }));

    await waitFor(() => expect(screen.getByText('New Chapter')).toBeInTheDocument());
    expect(screen.queryByText('Chapter One')).not.toBeInTheDocument();
  });

  it('shows an error when refresh fails', async () => {
    updateTocStructure.mockRejectedValue(new Error('Refresh error'));
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    fireEvent.click(screen.getByRole('button', { name: /refresh content/i }));

    await waitFor(() =>
      expect(screen.getByText(/failed to refresh table of contents/i)).toBeInTheDocument()
    );
  });

  it('disables the Refresh button while refreshing', async () => {
    updateTocStructure.mockReturnValue(new Promise(() => {})); // never resolves
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    fireEvent.click(screen.getByRole('button', { name: /refresh content/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /refresh/i })).toBeDisabled()
    );
  });
});

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — full-content modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTocStructure.mockResolvedValue({ data: MOCK_TOC });
    getIdeas.mockResolvedValue({ data: MOCK_IDEAS });
  });

  it('opens the modal when an idea item is clicked', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('First Idea'));

    fireEvent.click(screen.getByRole('button', { name: /view details for first idea/i }));

    // Modal is open — the role=dialog container appears
    await waitFor(() => {
      const allMatches = screen.getAllByText('Content of first idea');
      // At least two: one in the card preview, one in the modal
      expect(allMatches.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('shows the idea title in the modal header', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('First Idea'));

    fireEvent.click(screen.getByRole('button', { name: /view details for first idea/i }));

    // Title appears in both the card and the modal header
    await waitFor(() =>
      expect(screen.getAllByText('First Idea').length).toBeGreaterThanOrEqual(2)
    );
  });

  it('closes the modal when the close button (aria-label Close modal) is clicked', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('First Idea'));

    fireEvent.click(screen.getByRole('button', { name: /view details for first idea/i }));
    await waitFor(() => screen.getByRole('button', { name: /^close modal$/i }));

    fireEvent.click(screen.getByRole('button', { name: /^close modal$/i }));

    // After close, only one instance of the text remains (the card preview)
    await waitFor(() =>
      expect(screen.getAllByText('Content of first idea').length).toBe(1)
    );
  });

  it('closes the modal when the bottom "Close" button is clicked', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('First Idea'));

    fireEvent.click(screen.getByRole('button', { name: /view details for first idea/i }));
    await waitFor(() => screen.getByRole('button', { name: /^close$/i }));

    fireEvent.click(screen.getByRole('button', { name: /^close$/i }));

    await waitFor(() =>
      expect(screen.getAllByText('Content of first idea').length).toBe(1)
    );
  });
});

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — markdown export', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Restore default useBook implementation after any per-test override
    useBook.mockImplementation(() => ({ selectedBook: null, books: [], setSelectedBook: vi.fn() }));
    getTocStructure.mockResolvedValue({ data: MOCK_TOC });
    getIdeas.mockResolvedValue({ data: MOCK_IDEAS });
    getBookImpactComments.mockResolvedValue({ data: [] });
  });

  it('renders the "Export MD" button', async () => {
    render(<TableOfContents />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /export as markdown/i })).toBeInTheDocument()
    );
  });

  it('disables the Export MD button when there is no content', async () => {
    getTocStructure.mockResolvedValue({ data: [] });
    render(<TableOfContents />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /export as markdown/i })).toBeDisabled()
    );
  });

  it('triggers a file download with a .md filename when Export MD is clicked', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    // Set up download mocks AFTER render so React's own createElement calls are unaffected
    const mockClick = vi.fn();
    const mockAnchor = { href: '', download: '', click: mockClick };
    const origCreateElement = document.createElement.bind(document);
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-url');
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tag) =>
      tag === 'a' ? mockAnchor : origCreateElement(tag)
    );

    try {
      fireEvent.click(screen.getByRole('button', { name: /export as markdown/i }));

      expect(createObjectURLSpy).toHaveBeenCalledWith(expect.any(Blob));
      expect(mockAnchor.download).toMatch(/\.md$/);
      expect(mockClick).toHaveBeenCalled();
      expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url');
    } finally {
      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
      createElementSpy.mockRestore();
    }
  });

  it('includes the book title in the filename when a book is selected', async () => {
    useBook.mockImplementation(() => ({ selectedBook: { id: 1, title: 'My Book' }, books: [], setSelectedBook: vi.fn() }));

    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    const mockAnchor = { href: '', download: '', click: vi.fn() };
    const origCreateElement = document.createElement.bind(document);
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:url');
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tag) =>
      tag === 'a' ? mockAnchor : origCreateElement(tag)
    );

    try {
      fireEvent.click(screen.getByRole('button', { name: /export as markdown/i }));
      expect(mockAnchor.download).toMatch(/My_Book\.md$/);
    } finally {
      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
      createElementSpy.mockRestore();
    }
  });

  it('does not call getBookImpactComments when no book is selected', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));
    expect(getBookImpactComments).not.toHaveBeenCalled();
  });

  it('includes idea titles and content in the exported markdown', async () => {
    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    let capturedBlob;
    const origCreateElement = document.createElement.bind(document);
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      capturedBlob = blob;
      return 'blob:url';
    });
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tag) =>
      tag === 'a' ? { href: '', download: '', click: vi.fn() } : origCreateElement(tag)
    );

    try {
      fireEvent.click(screen.getByRole('button', { name: /export as markdown/i }));

      const text = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.readAsText(capturedBlob);
      });
      expect(text).toContain('Chapter One');
      expect(text).toContain('First Idea');
      expect(text).toContain('Content of first idea');
      // Tags: semicolons converted to ", "
      expect(text).toContain('**Tags:** ai, hardware');
      // Votes: positive score formatted with +
      expect(text).toContain('**Votes:** +4');
      // Second Idea has no tags, negative score
      expect(text).toContain('**Votes:** -2');
      expect(text).not.toContain('**Tags:** null');
    } finally {
      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
      createElementSpy.mockRestore();
    }
  });

  it('includes impact comments in the exported markdown when a book is selected', async () => {
    useBook.mockImplementation(() => ({
      selectedBook: { id: 1, title: 'My Book' },
      books: [],
      setSelectedBook: vi.fn(),
    }));
    getBookImpactComments.mockResolvedValue({
      data: [
        { id: 1, idea_id: 1, idea_title: 'First Idea', username: 'alice', content: 'Big societal impact', created_at: '2026-01-01' },
      ],
    });

    render(<TableOfContents />);
    await waitFor(() => screen.getByText('Chapter One'));

    let capturedBlob;
    const origCreateElement = document.createElement.bind(document);
    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      capturedBlob = blob;
      return 'blob:url';
    });
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockReturnValue(undefined);
    const createElementSpy = vi.spyOn(document, 'createElement').mockImplementation((tag) =>
      tag === 'a' ? { href: '', download: '', click: vi.fn() } : origCreateElement(tag)
    );

    try {
      fireEvent.click(screen.getByRole('button', { name: /export as markdown/i }));

      const text = await new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.readAsText(capturedBlob);
      });
      expect(text).toContain('**Impacts:**');
      expect(text).toContain('- alice : Big societal impact');
    } finally {
      createObjectURLSpy.mockRestore();
      revokeObjectURLSpy.mockRestore();
      createElementSpy.mockRestore();
    }
  });
});
