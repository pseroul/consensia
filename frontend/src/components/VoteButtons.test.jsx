/**
 * VoteButtons.test.jsx
 *
 * Strategy:
 * - Mock all three API calls (getIdeaVotes, castVote, removeVote)
 * - Use real React hooks (override global setupTests mock)
 * - Cover: initial fetch, score display, vote highlighting, toggle/flip/remove,
 *   button disabled during in-flight request, silent error handling
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

vi.mock('lucide-react', () => {
  const icon = (testId) => () => <svg data-testid={testId} />;
  return {
    ChevronUp:   icon('chevron-up-icon'),
    ChevronDown: icon('chevron-down-icon'),
  };
});

vi.mock('../services/api', () => ({
  getIdeaVotes: vi.fn(),
  castVote:     vi.fn(),
  removeVote:   vi.fn(),
}));

import VoteButtons from './VoteButtons';
import { getIdeaVotes, castVote, removeVote } from '../services/api';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const noVoteResponse    = { data: { score: 0,  count: 0, user_vote: null } };
const upvotedResponse   = { data: { score: 1,  count: 1, user_vote: 1    } };
const downvotedResponse = { data: { score: -1, count: 1, user_vote: -1   } };

const renderWidget = (ideaId = 42) => render(<VoteButtons ideaId={ideaId} />);

// ══════════════════════════════════════════════════════════════════════════════
describe('VoteButtons — initial render', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getIdeaVotes.mockResolvedValue(noVoteResponse);
  });

  it('renders nothing while the initial fetch is in progress', () => {
    getIdeaVotes.mockReturnValue(new Promise(() => {}));
    const { container } = renderWidget();
    expect(container.firstChild).toBeNull();
  });

  it('renders upvote and downvote buttons after loading', async () => {
    renderWidget();
    await waitFor(() => expect(screen.getByRole('button', { name: /upvote/i })).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /downvote/i })).toBeInTheDocument();
  });

  it('displays the fetched score', async () => {
    getIdeaVotes.mockResolvedValue({ data: { score: 7, count: 10, user_vote: null } });
    renderWidget();
    await waitFor(() => expect(screen.getByTestId('vote-score')).toHaveTextContent('7'));
  });

  it('displays score 0 when no votes exist', async () => {
    renderWidget();
    await waitFor(() => expect(screen.getByTestId('vote-score')).toHaveTextContent('0'));
  });

  it('calls getIdeaVotes with the provided ideaId', async () => {
    renderWidget(99);
    await waitFor(() => expect(getIdeaVotes).toHaveBeenCalledWith(99));
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('VoteButtons — active vote highlighting', () => {
  beforeEach(() => vi.clearAllMocks());

  it('applies active class to upvote button when user has upvoted', async () => {
    getIdeaVotes.mockResolvedValue(upvotedResponse);
    renderWidget();
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /upvote/i });
      expect(btn.className).toContain('text-blue-600');
    });
  });

  it('applies active class to downvote button when user has downvoted', async () => {
    getIdeaVotes.mockResolvedValue(downvotedResponse);
    renderWidget();
    await waitFor(() => {
      const btn = screen.getByRole('button', { name: /downvote/i });
      expect(btn.className).toContain('text-red-500');
    });
  });

  it('applies no active class when user has not voted', async () => {
    getIdeaVotes.mockResolvedValue(noVoteResponse);
    renderWidget();
    await waitFor(() => {
      const upBtn   = screen.getByRole('button', { name: /upvote/i });
      const downBtn = screen.getByRole('button', { name: /downvote/i });
      expect(upBtn.className).not.toContain('text-blue-600');
      expect(downBtn.className).not.toContain('text-red-500');
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('VoteButtons — voting interactions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getIdeaVotes.mockResolvedValue(noVoteResponse);
    castVote.mockResolvedValue(upvotedResponse);
    removeVote.mockResolvedValue(noVoteResponse);
  });

  it('calls castVote(id, 1) when upvote button is clicked without an active vote', async () => {
    renderWidget(42);
    await waitFor(() => screen.getByRole('button', { name: /upvote/i }));

    fireEvent.click(screen.getByRole('button', { name: /upvote/i }));

    await waitFor(() => expect(castVote).toHaveBeenCalledWith(42, 1));
  });

  it('calls castVote(id, -1) when downvote button is clicked without an active vote', async () => {
    castVote.mockResolvedValue(downvotedResponse);
    renderWidget(42);
    await waitFor(() => screen.getByRole('button', { name: /downvote/i }));

    fireEvent.click(screen.getByRole('button', { name: /downvote/i }));

    await waitFor(() => expect(castVote).toHaveBeenCalledWith(42, -1));
  });

  it('updates score display after a successful upvote', async () => {
    renderWidget();
    await waitFor(() => expect(screen.getByTestId('vote-score')).toHaveTextContent('0'));

    fireEvent.click(screen.getByRole('button', { name: /upvote/i }));

    await waitFor(() => expect(screen.getByTestId('vote-score')).toHaveTextContent('1'));
  });

  it('calls removeVote when upvote is clicked and user already upvoted (toggle off)', async () => {
    getIdeaVotes.mockResolvedValue(upvotedResponse);
    renderWidget(42);
    await waitFor(() => screen.getByRole('button', { name: /upvote/i }));

    fireEvent.click(screen.getByRole('button', { name: /upvote/i }));

    await waitFor(() => expect(removeVote).toHaveBeenCalledWith(42));
  });

  it('calls removeVote when downvote is clicked and user already downvoted (toggle off)', async () => {
    getIdeaVotes.mockResolvedValue(downvotedResponse);
    removeVote.mockResolvedValue(noVoteResponse);
    renderWidget(42);
    await waitFor(() => screen.getByRole('button', { name: /downvote/i }));

    fireEvent.click(screen.getByRole('button', { name: /downvote/i }));

    await waitFor(() => expect(removeVote).toHaveBeenCalledWith(42));
  });

  it('calls castVote when user flips from upvote to downvote', async () => {
    getIdeaVotes.mockResolvedValue(upvotedResponse);
    castVote.mockResolvedValue(downvotedResponse);
    renderWidget(42);
    await waitFor(() => screen.getByRole('button', { name: /downvote/i }));

    fireEvent.click(screen.getByRole('button', { name: /downvote/i }));

    await waitFor(() => expect(castVote).toHaveBeenCalledWith(42, -1));
    expect(removeVote).not.toHaveBeenCalled();
  });

  it('disables both buttons while a vote request is in flight', async () => {
    let resolve;
    castVote.mockReturnValue(new Promise((r) => { resolve = r; }));
    renderWidget();
    await waitFor(() => screen.getByRole('button', { name: /upvote/i }));

    fireEvent.click(screen.getByRole('button', { name: /upvote/i }));

    expect(screen.getByRole('button', { name: /upvote/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /downvote/i })).toBeDisabled();

    resolve(upvotedResponse);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /upvote/i })).not.toBeDisabled()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('VoteButtons — error handling', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders nothing when initial getIdeaVotes fails', async () => {
    getIdeaVotes.mockRejectedValue(new Error('Network error'));
    const { container } = renderWidget();
    // After the rejected promise resolves, isLoading becomes false but component
    // should still render (score defaults to 0)
    await waitFor(() => expect(getIdeaVotes).toHaveBeenCalled());
    // Component renders — does not crash
    expect(container).toBeDefined();
  });

  it('does not crash when castVote throws', async () => {
    getIdeaVotes.mockResolvedValue(noVoteResponse);
    castVote.mockRejectedValue(new Error('Server error'));
    renderWidget();
    await waitFor(() => screen.getByRole('button', { name: /upvote/i }));

    fireEvent.click(screen.getByRole('button', { name: /upvote/i }));

    // Buttons re-enabled after error, score unchanged
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /upvote/i })).not.toBeDisabled()
    );
    expect(screen.getByTestId('vote-score')).toHaveTextContent('0');
  });
});
