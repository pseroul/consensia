import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, BookOpen, Plus, Trash2, UserPlus, UserMinus, Loader2, ChevronRight, X } from 'lucide-react';
import { getBooks, createBook, deleteBook, getBookAuthors, addBookAuthor, removeBookAuthor, getUsers } from '../services/api';
import { useBook } from '../contexts/BookContext';

// ─── Confirmation modal ────────────────────────────────────────────────────────
const ConfirmModal = ({ isOpen, onClose, onConfirm, message }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black bg-opacity-70">
      <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl border border-gray-100">
        <p className="text-gray-800 mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};

// ─── Authors panel for a single book ──────────────────────────────────────────
const AuthorsPanel = ({ book, allUsers, onClose }) => {
  const [authors, setAuthors] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [addingUserId, setAddingUserId] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const fetchAuthors = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await getBookAuthors(book.id);
      setAuthors(res.data);
    } catch {
      setError('Failed to load authors.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchAuthors(); }, [book.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const authorIds = new Set(authors.map((a) => a.id));
  const eligibleUsers = allUsers.filter((u) => !authorIds.has(u.id));

  const handleAdd = async () => {
    if (!addingUserId) return;
    setIsSaving(true);
    try {
      await addBookAuthor(book.id, Number(addingUserId));
      setAddingUserId('');
      await fetchAuthors();
    } catch {
      setError('Failed to add author.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemove = async (userId) => {
    try {
      await removeBookAuthor(book.id, userId);
      await fetchAuthors();
    } catch {
      setError('Failed to remove author.');
    }
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black bg-opacity-70">
      <div
        data-testid="authors-panel"
        className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-gray-900">Authors — {book.title}</h2>
          <button
            onClick={onClose}
            type="button"
            aria-label="Close"
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X size={24} className="text-gray-400" />
          </button>
        </div>

        {error && <p className="mb-3 text-sm text-red-600">{error}</p>}

        {/* Current authors list */}
        {isLoading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="animate-spin text-blue-600" size={24} />
          </div>
        ) : (
          <ul className="mb-6 space-y-2">
            {authors.length === 0 && (
              <li className="text-sm text-gray-400 italic">No authors yet.</li>
            )}
            {authors.map((author) => (
              <li
                key={author.id}
                className="flex items-center justify-between p-2 rounded-lg bg-gray-50"
              >
                <div>
                  <span className="font-medium text-gray-800">{author.username}</span>
                  <span className="text-xs text-gray-500 ml-2">{author.email}</span>
                </div>
                <button
                  onClick={() => handleRemove(author.id)}
                  aria-label={`Remove ${author.username}`}
                  className="p-1 hover:bg-red-50 rounded-full transition-colors"
                >
                  <UserMinus size={16} className="text-red-500" />
                </button>
              </li>
            ))}
          </ul>
        )}

        {/* Add author */}
        {eligibleUsers.length > 0 && (
          <div className="flex gap-2">
            <select
              data-testid="user-select"
              value={addingUserId}
              onChange={(e) => setAddingUserId(e.target.value)}
              className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a user to add...</option>
              {eligibleUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username} ({u.email})
                </option>
              ))}
            </select>
            <button
              onClick={handleAdd}
              disabled={!addingUserId || isSaving}
              aria-label="Add author"
              className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-3 py-2 rounded-lg flex items-center gap-1 transition-colors"
            >
              {isSaving ? <Loader2 className="animate-spin" size={16} /> : <UserPlus size={16} />}
            </button>
          </div>
        )}

        {eligibleUsers.length === 0 && !isLoading && (
          <p className="text-sm text-gray-400 italic">All registered users are already authors.</p>
        )}
      </div>
    </div>
  );
};

// ─── Main page ─────────────────────────────────────────────────────────────────
const BooksPage = () => {
  const { books, setBooks, setSelectedBook } = useBook() ?? {};

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newTitle, setNewTitle] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null); // book object to delete
  const [managingAuthors, setManagingAuthors] = useState(null); // book object
  const [allUsers, setAllUsers] = useState([]);

  const fetchBooks = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [booksRes, usersRes] = await Promise.all([getBooks(), getUsers()]);
      setBooks(booksRes.data);
      setAllUsers(usersRes.data);
    } catch {
      setError('Failed to load books.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchBooks(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setIsCreating(true);
    try {
      await createBook({ title: newTitle.trim() });
      setNewTitle('');
      await fetchBooks();
    } catch {
      setError('Failed to create book.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await deleteBook(confirmDelete.id);
      if (setSelectedBook) setSelectedBook((prev) => (prev?.id === confirmDelete.id ? null : prev));
      setConfirmDelete(null);
      await fetchBooks();
    } catch {
      setError('Failed to delete book.');
      setConfirmDelete(null);
    }
  };

  return (
    <div className="min-h-screen bg-white p-4 md:p-12">
      <div className="max-w-3xl mx-auto">

        {/* Back link */}
        <Link
          to="/dashboard"
          className="flex items-center gap-2 text-gray-500 hover:text-blue-600 transition-colors mb-8 group"
          aria-label="Back to dashboard"
        >
          <ArrowLeft size={20} className="group-hover:-translate-x-1 transition-transform" />
          <span>Back to Dashboard</span>
        </Link>

        {/* Page header */}
        <div className="flex items-center gap-4 mb-10 border-b border-gray-100 pb-6">
          <div className="bg-blue-50 p-3 rounded-full text-blue-600">
            <BookOpen size={28} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">My Books</h1>
            <p className="text-gray-500 italic">{books?.length ?? 0} book{books?.length !== 1 ? 's' : ''}</p>
          </div>
        </div>

        {/* Create new book */}
        <form onSubmit={handleCreate} className="flex gap-2 mb-8">
          <input
            type="text"
            placeholder="New book title..."
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            className="flex-1 border border-gray-200 rounded-xl px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50 text-gray-900"
            aria-label="New book title"
          />
          <button
            type="submit"
            disabled={!newTitle.trim() || isCreating}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white px-4 py-2 rounded-xl flex items-center gap-2 transition-colors"
            aria-label="Create book"
          >
            {isCreating ? <Loader2 className="animate-spin" size={18} /> : <Plus size={18} />}
            <span>Create</span>
          </button>
        </form>

        {/* Error banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg">{error}</div>
        )}

        {/* Books list */}
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin text-blue-600" size={32} />
          </div>
        ) : (
          <div className="space-y-2">
            {books?.length === 0 && (
              <p className="text-center text-gray-400 py-10">No books yet. Create your first one above.</p>
            )}
            {books?.map((book) => (
              <div
                key={book.id}
                className="flex items-center justify-between p-4 bg-white border border-gray-100 rounded-xl shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="flex items-center gap-3">
                  <ChevronRight size={18} className="text-blue-400" />
                  <span className="font-medium text-gray-800">{book.title}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setManagingAuthors(book)}
                    aria-label={`Manage authors of ${book.title}`}
                    className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors"
                  >
                    <UserPlus size={16} />
                    <span className="hidden sm:inline">Authors</span>
                  </button>
                  <button
                    onClick={() => setConfirmDelete(book)}
                    aria-label={`Delete book ${book.title}`}
                    className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirmation */}
      <ConfirmModal
        isOpen={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        onConfirm={handleDelete}
        message={`Delete "${confirmDelete?.title}"? This cannot be undone.`}
      />

      {/* Authors management panel */}
      {managingAuthors && (
        <AuthorsPanel
          book={managingAuthors}
          allUsers={allUsers}
          onClose={() => setManagingAuthors(null)}
        />
      )}
    </div>
  );
};

export default BooksPage;
