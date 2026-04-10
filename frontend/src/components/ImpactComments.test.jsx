/**
 * ImpactComments.test.jsx
 *
 * Strategy:
 * - Mock getImpactComments, createImpactComment, deleteImpactComment from api
 * - Mock useAuth to control the current user's email
 * - Cover: loading state, empty list, comment list, add comment, delete own
 *   comment, hide delete for others' comments, 403 error on add
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('lucide-react', () => {
  const icon = (testId) => ({ className: _className, size: _size, ...rest }) =>
    <svg data-testid={testId} {...rest} />;
  return {
    Trash2: icon('trash-icon'),
    Loader2: icon('loader-icon'),
  };
});

vi.mock('../services/api', () => ({
  getImpactComments: vi.fn(),
  createImpactComment: vi.fn(),
  deleteImpactComment: vi.fn(),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}));

import ImpactComments from './ImpactComments';
import { getImpactComments, createImpactComment, deleteImpactComment } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

// ─── Fixtures ─────────────────────────────────────────────────────────────────

const ALICE_EMAIL = 'alice@example.com';
const BOB_EMAIL = 'bob@example.com';

const makeComment = (overrides = {}) => ({
  id: 1,
  idea_id: 42,
  user_id: 1,
  username: 'alice',
  user_email: ALICE_EMAIL,
  content: 'This is an impact',
  created_at: '2026-01-01 10:00:00',
  ...overrides,
});

const renderComponent = (ideaId = 42) => render(<ImpactComments ideaId={ideaId} />);

// ══════════════════════════════════════════════════════════════════════════════

describe('ImpactComments — loading and empty state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { email: ALICE_EMAIL } });
  });

  it('shows a loader while fetching', () => {
    getImpactComments.mockReturnValue(new Promise(() => {}));
    renderComponent();
    expect(screen.getByTestId('loader-icon')).toBeInTheDocument();
  });

  it('shows empty message when no comments exist', async () => {
    getImpactComments.mockResolvedValue({ data: [] });
    renderComponent();
    await waitFor(() =>
      expect(screen.getByText(/aucun impact/i)).toBeInTheDocument()
    );
  });

  it('calls getImpactComments with the ideaId on mount', async () => {
    getImpactComments.mockResolvedValue({ data: [] });
    renderComponent(99);
    await waitFor(() => expect(getImpactComments).toHaveBeenCalledWith(99));
  });
});

describe('ImpactComments — comment list display', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { email: ALICE_EMAIL } });
  });

  it('displays comment content and username', async () => {
    getImpactComments.mockResolvedValue({ data: [makeComment()] });
    renderComponent();
    await waitFor(() => {
      expect(screen.getByText('This is an impact')).toBeInTheDocument();
      expect(screen.getByText('alice')).toBeInTheDocument();
    });
  });

  it('shows delete button for own comment', async () => {
    getImpactComments.mockResolvedValue({ data: [makeComment()] });
    renderComponent();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /supprimer/i })).toBeInTheDocument()
    );
  });

  it('hides delete button for other users comments', async () => {
    getImpactComments.mockResolvedValue({
      data: [makeComment({ username: 'bob', user_email: BOB_EMAIL })],
    });
    renderComponent();
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: /supprimer/i })).not.toBeInTheDocument()
    );
  });

  it('renders multiple comments', async () => {
    getImpactComments.mockResolvedValue({
      data: [
        makeComment({ id: 1, content: 'First impact' }),
        makeComment({ id: 2, content: 'Second impact', username: 'bob', user_email: BOB_EMAIL }),
      ],
    });
    renderComponent();
    await waitFor(() => {
      expect(screen.getByText('First impact')).toBeInTheDocument();
      expect(screen.getByText('Second impact')).toBeInTheDocument();
    });
  });
});

describe('ImpactComments — add comment', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { email: ALICE_EMAIL } });
    getImpactComments.mockResolvedValue({ data: [] });
  });

  it('submitting the form calls createImpactComment and appends the new comment', async () => {
    const newComment = makeComment({ content: 'New impact' });
    createImpactComment.mockResolvedValue({ data: newComment });
    renderComponent();

    await waitFor(() => screen.getByPlaceholderText(/ajouter un impact/i));

    fireEvent.change(screen.getByPlaceholderText(/ajouter un impact/i), {
      target: { value: 'New impact' },
    });
    fireEvent.click(screen.getByRole('button', { name: /ajouter un impact/i }));

    await waitFor(() => {
      expect(createImpactComment).toHaveBeenCalledWith(42, 'New impact');
      expect(screen.getByText('New impact')).toBeInTheDocument();
    });
  });

  it('submit button is disabled when textarea is empty', async () => {
    renderComponent();
    await waitFor(() => screen.getByRole('button', { name: /ajouter un impact/i }));
    expect(screen.getByRole('button', { name: /ajouter un impact/i })).toBeDisabled();
  });

  it('shows 403 error message when user is not a book author', async () => {
    createImpactComment.mockRejectedValue({ response: { status: 403 } });
    renderComponent();

    await waitFor(() => screen.getByPlaceholderText(/ajouter un impact/i));

    fireEvent.change(screen.getByPlaceholderText(/ajouter un impact/i), {
      target: { value: 'Forbidden comment' },
    });
    fireEvent.click(screen.getByRole('button', { name: /ajouter un impact/i }));

    await waitFor(() =>
      expect(screen.getByText(/n'avez pas accès/i)).toBeInTheDocument()
    );
  });

  it('shows generic error message on other failures', async () => {
    createImpactComment.mockRejectedValue({ response: { status: 500 } });
    renderComponent();

    await waitFor(() => screen.getByPlaceholderText(/ajouter un impact/i));

    fireEvent.change(screen.getByPlaceholderText(/ajouter un impact/i), {
      target: { value: 'Broken comment' },
    });
    fireEvent.click(screen.getByRole('button', { name: /ajouter un impact/i }));

    await waitFor(() =>
      expect(screen.getByText(/erreur est survenue/i)).toBeInTheDocument()
    );
  });
});

describe('ImpactComments — delete comment', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ user: { email: ALICE_EMAIL } });
  });

  it('clicking delete removes the comment from the list', async () => {
    getImpactComments.mockResolvedValue({ data: [makeComment()] });
    deleteImpactComment.mockResolvedValue({});
    renderComponent();

    await waitFor(() => screen.getByRole('button', { name: /supprimer/i }));
    fireEvent.click(screen.getByRole('button', { name: /supprimer/i }));

    await waitFor(() =>
      expect(screen.queryByText('This is an impact')).not.toBeInTheDocument()
    );
    expect(deleteImpactComment).toHaveBeenCalledWith(1);
  });

  it('keeps comment in list if delete fails', async () => {
    getImpactComments.mockResolvedValue({ data: [makeComment()] });
    deleteImpactComment.mockRejectedValue(new Error('Network error'));
    renderComponent();

    await waitFor(() => screen.getByRole('button', { name: /supprimer/i }));
    fireEvent.click(screen.getByRole('button', { name: /supprimer/i }));

    await waitFor(() => expect(deleteImpactComment).toHaveBeenCalled());
    expect(screen.getByText('This is an impact')).toBeInTheDocument();
  });
});
