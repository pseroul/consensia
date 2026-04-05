/**
 * BooksPage.test.jsx
 * Unit tests for the Books management page.
 *
 * Coverage:
 * - Initial render (loading, heading, create form)
 * - Listing books fetched from API
 * - Creating a new book
 * - Deleting a book with confirmation
 * - Opening the authors panel
 * - Adding / removing authors inside the panel
 * - Error handling
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ─── Real React hooks ─────────────────────────────────────────────────────────
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

// ─── Icons ────────────────────────────────────────────────────────────────────
vi.mock('lucide-react', () => {
  const icon = (id) => () => <svg data-testid={id} />;
  return {
    ArrowLeft:   icon('arrow-left-icon'),
    BookOpen:    icon('book-open-icon'),
    Plus:        icon('plus-icon'),
    Trash2:      icon('trash-icon'),
    UserPlus:    icon('user-plus-icon'),
    UserMinus:   icon('user-minus-icon'),
    Loader2:     icon('loader-icon'),
    ChevronRight: icon('chevron-right-icon'),
    X:           icon('x-icon'),
  };
});

// ─── Router ───────────────────────────────────────────────────────────────────
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
  };
});

// ─── BookContext ──────────────────────────────────────────────────────────────
const mockSetBooks = vi.fn();
const mockSetSelectedBook = vi.fn();
let mockBooks = [];
vi.mock('../contexts/BookContext', () => ({
  useBook: () => ({
    books: mockBooks,
    setBooks: mockSetBooks,
    setSelectedBook: mockSetSelectedBook,
  }),
}));

// ─── API ──────────────────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  getBooks:        vi.fn(),
  createBook:      vi.fn(),
  deleteBook:      vi.fn(),
  getBookAuthors:  vi.fn(),
  addBookAuthor:   vi.fn(),
  removeBookAuthor: vi.fn(),
  getUsers:        vi.fn(),
}));

import BooksPage from './BooksPage';
import {
  getBooks, createBook, deleteBook,
  getBookAuthors, addBookAuthor, removeBookAuthor, getUsers,
} from '../services/api';

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const BOOKS = [
  { id: 1, title: 'Book Alpha' },
  { id: 2, title: 'Book Beta' },
];
const USERS = [
  { id: 10, username: 'alice', email: 'alice@example.com' },
  { id: 20, username: 'bob',   email: 'bob@example.com' },
];
const AUTHORS = [{ id: 10, username: 'alice', email: 'alice@example.com' }];

const setupMocks = () => {
  mockBooks = [...BOOKS];
  getBooks.mockResolvedValue({ data: BOOKS });
  getUsers.mockResolvedValue({ data: USERS });
  getBookAuthors.mockResolvedValue({ data: AUTHORS });
  createBook.mockResolvedValue({ data: { id: 3 } });
  deleteBook.mockResolvedValue({});
  addBookAuthor.mockResolvedValue({});
  removeBookAuthor.mockResolvedValue({});
};

// ══════════════════════════════════════════════════════════════════════════════
describe('BooksPage — initial render', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('shows a loading spinner while fetching', () => {
    getBooks.mockReturnValue(new Promise(() => {}));
    render(<BooksPage />);
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
  });

  it('renders the page heading "My Books"', async () => {
    render(<BooksPage />);
    await waitFor(() => expect(screen.getByText('My Books')).toBeInTheDocument());
  });

  it('renders the "Back to Dashboard" link', async () => {
    render(<BooksPage />);
    await waitFor(() =>
      expect(screen.getByRole('link', { name: /back to dashboard/i })).toHaveAttribute('href', '/dashboard')
    );
  });

  it('renders the create-book input', async () => {
    render(<BooksPage />);
    await waitFor(() =>
      expect(screen.getByRole('textbox', { name: /new book title/i })).toBeInTheDocument()
    );
  });

  it('renders the "Create" button disabled when input is empty', async () => {
    render(<BooksPage />);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /create book/i })).toBeDisabled()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('BooksPage — book list', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('displays all fetched books', async () => {
    render(<BooksPage />);
    await waitFor(() => {
      expect(screen.getByText('Book Alpha')).toBeInTheDocument();
      expect(screen.getByText('Book Beta')).toBeInTheDocument();
    });
  });

  it('shows empty state when no books exist', async () => {
    getBooks.mockResolvedValue({ data: [] });
    mockBooks = [];
    render(<BooksPage />);
    await waitFor(() =>
      expect(screen.getByText(/no books yet/i)).toBeInTheDocument()
    );
  });

  it('calls getBooks and getUsers on mount', async () => {
    render(<BooksPage />);
    await waitFor(() => expect(getBooks).toHaveBeenCalledTimes(1));
    expect(getUsers).toHaveBeenCalledTimes(1);
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('BooksPage — create book', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('enables the Create button when title is typed', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByRole('textbox', { name: /new book title/i }));
    fireEvent.change(screen.getByRole('textbox', { name: /new book title/i }), {
      target: { value: 'New Book' },
    });
    expect(screen.getByRole('button', { name: /create book/i })).not.toBeDisabled();
  });

  it('calls createBook and refreshes on form submit', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByRole('textbox', { name: /new book title/i }));

    fireEvent.change(screen.getByRole('textbox', { name: /new book title/i }), {
      target: { value: 'New Book' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create book/i }));

    await waitFor(() => expect(createBook).toHaveBeenCalledWith({ title: 'New Book' }));
    expect(getBooks).toHaveBeenCalledTimes(2); // initial + after create
  });

  it('clears the input after creating', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByRole('textbox', { name: /new book title/i }));

    const input = screen.getByRole('textbox', { name: /new book title/i });
    fireEvent.change(input, { target: { value: 'New Book' } });
    fireEvent.click(screen.getByRole('button', { name: /create book/i }));

    await waitFor(() => expect(createBook).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(input).toHaveValue(''));
  });

  it('shows error banner when createBook fails', async () => {
    createBook.mockRejectedValue(new Error('Server error'));
    render(<BooksPage />);
    await waitFor(() => screen.getByRole('textbox', { name: /new book title/i }));

    fireEvent.change(screen.getByRole('textbox', { name: /new book title/i }), {
      target: { value: 'Bad Book' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create book/i }));

    await waitFor(() => expect(screen.getByText(/failed to create book/i)).toBeInTheDocument());
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('BooksPage — delete book', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('shows a confirmation modal when delete is clicked', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /delete book book alpha/i }));
    expect(screen.getByText(/delete "book alpha"/i)).toBeInTheDocument();
  });

  it('calls deleteBook and refreshes when confirmed', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /delete book book alpha/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));

    await waitFor(() => expect(deleteBook).toHaveBeenCalledWith(1));
    expect(getBooks).toHaveBeenCalledTimes(2);
  });

  it('does NOT call deleteBook when cancel is clicked', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /delete book book alpha/i }));
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    expect(deleteBook).not.toHaveBeenCalled();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('BooksPage — authors panel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('opens the authors panel when "Authors" is clicked', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /manage authors of book alpha/i }));

    await waitFor(() => expect(screen.getByTestId('authors-panel')).toBeInTheDocument());
  });

  it('displays current authors in the panel', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /manage authors of book alpha/i }));

    await waitFor(() => expect(screen.getByText('alice')).toBeInTheDocument());
  });

  it('closes the panel when X is clicked', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /manage authors of book alpha/i }));
    await waitFor(() => screen.getByTestId('authors-panel'));

    fireEvent.click(screen.getByRole('button', { name: /^close$/i }));
    expect(screen.queryByTestId('authors-panel')).not.toBeInTheDocument();
  });

  it('calls addBookAuthor when a user is selected and added', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /manage authors of book alpha/i }));
    await waitFor(() => screen.getByTestId('user-select'));

    fireEvent.change(screen.getByTestId('user-select'), { target: { value: '20' } });
    fireEvent.click(screen.getByRole('button', { name: /add author/i }));

    await waitFor(() => expect(addBookAuthor).toHaveBeenCalledWith(1, 20));
  });

  it('calls removeBookAuthor when remove button is clicked', async () => {
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /manage authors of book alpha/i }));
    await waitFor(() => screen.getByText('alice'));

    fireEvent.click(screen.getByRole('button', { name: /remove alice/i }));
    await waitFor(() => expect(removeBookAuthor).toHaveBeenCalledWith(1, 10));
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('BooksPage — error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('shows error banner when initial load fails', async () => {
    getBooks.mockRejectedValue(new Error('Network error'));
    render(<BooksPage />);
    await waitFor(() => expect(screen.getByText(/failed to load books/i)).toBeInTheDocument());
  });

  it('shows error banner when deleteBook fails', async () => {
    deleteBook.mockRejectedValue(new Error('Server error'));
    render(<BooksPage />);
    await waitFor(() => screen.getByText('Book Alpha'));

    fireEvent.click(screen.getByRole('button', { name: /delete book book alpha/i }));
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }));

    await waitFor(() => expect(screen.getByText(/failed to delete book/i)).toBeInTheDocument());
  });
});
