/**
 * BookSelector.test.jsx
 * Tests for the BookSelector dropdown component.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

vi.mock('lucide-react', () => ({
  BookOpen: () => <svg data-testid="book-open-icon" />,
}));

const mockSetSelectedBook = vi.fn();
let mockContextValue = { books: [], selectedBook: null, setSelectedBook: mockSetSelectedBook };

vi.mock('../contexts/BookContext', () => ({
  useBook: () => mockContextValue,
}));

import BookSelector from './BookSelector';

const BOOKS = [
  { id: 1, title: 'Book Alpha' },
  { id: 2, title: 'Book Beta' },
];

describe('BookSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockContextValue = { books: [], selectedBook: null, setSelectedBook: mockSetSelectedBook };
  });

  it('renders nothing when books list is empty', () => {
    const { container } = render(<BookSelector />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders the select dropdown when books are available', () => {
    mockContextValue = { books: BOOKS, selectedBook: null, setSelectedBook: mockSetSelectedBook };
    render(<BookSelector />);
    expect(screen.getByTestId('book-selector')).toBeInTheDocument();
  });

  it('renders "All Books" as default option', () => {
    mockContextValue = { books: BOOKS, selectedBook: null, setSelectedBook: mockSetSelectedBook };
    render(<BookSelector />);
    expect(screen.getByRole('option', { name: 'All Books' })).toBeInTheDocument();
  });

  it('renders one option per book', () => {
    mockContextValue = { books: BOOKS, selectedBook: null, setSelectedBook: mockSetSelectedBook };
    render(<BookSelector />);
    expect(screen.getByRole('option', { name: 'Book Alpha' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Book Beta' })).toBeInTheDocument();
  });

  it('shows selected book title in the dropdown', () => {
    mockContextValue = { books: BOOKS, selectedBook: BOOKS[0], setSelectedBook: mockSetSelectedBook };
    render(<BookSelector />);
    expect(screen.getByTestId('book-selector')).toHaveValue('1');
  });

  it('calls setSelectedBook with the chosen book when a book is selected', () => {
    mockContextValue = { books: BOOKS, selectedBook: null, setSelectedBook: mockSetSelectedBook };
    render(<BookSelector />);
    fireEvent.change(screen.getByTestId('book-selector'), { target: { value: '2' } });
    expect(mockSetSelectedBook).toHaveBeenCalledWith(BOOKS[1]);
  });

  it('calls setSelectedBook with null when "All Books" is selected', () => {
    mockContextValue = { books: BOOKS, selectedBook: BOOKS[0], setSelectedBook: mockSetSelectedBook };
    render(<BookSelector />);
    fireEvent.change(screen.getByTestId('book-selector'), { target: { value: '' } });
    expect(mockSetSelectedBook).toHaveBeenCalledWith(null);
  });
});
