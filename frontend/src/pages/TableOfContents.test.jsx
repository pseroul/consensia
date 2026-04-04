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

// ─── Mock API ─────────────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  getTocStructure:    vi.fn(),
  updateTocStructure: vi.fn(),
}));

import TableOfContents from './TableOfContents';
import { getTocStructure, updateTocStructure } from '../services/api';

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

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — initial render', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTocStructure.mockResolvedValue({ data: MOCK_TOC });
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

  it('shows the section count in the subtitle', async () => {
    render(<TableOfContents />);
    await waitFor(() => expect(screen.getByText('2 sections')).toBeInTheDocument());
  });
});

// ──────────────────────────────────────────────────────────────────────────────
describe('TableOfContents — error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
