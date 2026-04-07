/**
 * BookContext.test.jsx
 * Tests for the BookProvider and useBook hook.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

vi.mock('../services/api', () => ({
  getBooks: vi.fn(),
}));

import { BookProvider, useBook } from './BookContext';
import { getBooks } from '../services/api';

const Consumer = () => {
  const { books, selectedBook } = useBook();
  return (
    <div>
      <span data-testid="book-count">{books.length}</span>
      <span data-testid="selected">{selectedBook?.title ?? 'none'}</span>
    </div>
  );
};

describe('BookContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('access_token', 'test-token');
  });

  it('provides an empty books list initially before fetch resolves', () => {
    getBooks.mockReturnValue(new Promise(() => {}));
    render(
      <BookProvider>
        <Consumer />
      </BookProvider>
    );
    expect(screen.getByTestId('book-count')).toHaveTextContent('0');
  });

  it('fetches books on mount and exposes them', async () => {
    getBooks.mockResolvedValue({ data: [{ id: 1, title: 'Book A' }, { id: 2, title: 'Book B' }] });
    render(
      <BookProvider>
        <Consumer />
      </BookProvider>
    );
    await waitFor(() => expect(screen.getByTestId('book-count')).toHaveTextContent('2'));
  });

  it('does not call getBooks when no access_token is present', () => {
    localStorage.removeItem('access_token');
    getBooks.mockResolvedValue({ data: [] });
    render(
      <BookProvider>
        <Consumer />
      </BookProvider>
    );
    expect(getBooks).not.toHaveBeenCalled();
  });

  it('handles getBooks API error gracefully (stays empty)', async () => {
    getBooks.mockRejectedValue(new Error('Network error'));
    render(
      <BookProvider>
        <Consumer />
      </BookProvider>
    );
    await waitFor(() => expect(getBooks).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId('book-count')).toHaveTextContent('0');
  });

  it('starts with selectedBook as null', async () => {
    getBooks.mockResolvedValue({ data: [{ id: 1, title: 'Book A' }] });
    render(
      <BookProvider>
        <Consumer />
      </BookProvider>
    );
    await waitFor(() => expect(screen.getByTestId('book-count')).toHaveTextContent('1'));
    expect(screen.getByTestId('selected')).toHaveTextContent('none');
  });
});
