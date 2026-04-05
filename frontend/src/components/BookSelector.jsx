import React from 'react';
import { BookOpen } from 'lucide-react';
import { useBook } from '../contexts/BookContext';

const BookSelector = () => {
  const { books, selectedBook, setSelectedBook } = useBook();

  if (!books || books.length === 0) return null;

  return (
    <div className="flex items-center gap-2">
      <BookOpen size={16} className="text-gray-400 shrink-0" />
      <select
        data-testid="book-selector"
        value={selectedBook?.id ?? ''}
        onChange={(e) => {
          const id = e.target.value;
          setSelectedBook(id ? books.find((b) => String(b.id) === id) ?? null : null);
        }}
        className="text-sm border border-gray-200 rounded-lg px-2 py-1 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <option value="">All Books</option>
        {books.map((book) => (
          <option key={book.id} value={book.id}>
            {book.title}
          </option>
        ))}
      </select>
    </div>
  );
};

export default BookSelector;
