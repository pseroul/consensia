import React, { useState, useEffect } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';
import { getIdeaVotes, castVote, removeVote } from '../services/api';

/**
 * VoteButtons Component — upvote / downvote widget for a single idea.
 *
 * Fetches the current vote tally and the requesting user's own vote on mount,
 * then lets the user cast, flip, or retract their vote without reloading the
 * whole page.
 *
 * Toggling behaviour:
 *   - Click the already-active button → vote is removed (score reverts).
 *   - Click the other button → vote is switched in a single request.
 *
 * All API errors are swallowed silently so a voting failure never crashes the
 * surrounding idea card.
 *
 * @param {Object} props
 * @param {number|string} props.ideaId - ID of the idea to vote on.
 */
const VoteButtons = ({ ideaId }) => {
  const [score, setScore] = useState(0);
  const [userVote, setUserVote] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isVoting, setIsVoting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getIdeaVotes(ideaId)
      .then((res) => {
        if (!cancelled) {
          setScore(res.data.score);
          setUserVote(res.data.user_vote);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ideaId]);

  const handleVote = async (value) => {
    if (isVoting) return;
    setIsVoting(true);
    try {
      const res =
        userVote === value
          ? await removeVote(ideaId)
          : await castVote(ideaId, value);
      setScore(res.data.score);
      setUserVote(res.data.user_vote);
    } catch {
      // silent fail — voting is non-critical
    } finally {
      setIsVoting(false);
    }
  };

  if (isLoading) return null;

  return (
    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
      <button
        onClick={() => handleVote(1)}
        disabled={isVoting}
        aria-label="Upvote"
        className={`p-1 rounded transition-colors disabled:opacity-50 ${
          userVote === 1
            ? 'text-blue-600'
            : 'text-gray-400 hover:text-blue-500'
        }`}
      >
        <ChevronUp size={18} />
      </button>
      <span
        data-testid="vote-score"
        className="text-sm font-semibold text-gray-700 min-w-[1.5rem] text-center"
      >
        {score}
      </span>
      <button
        onClick={() => handleVote(-1)}
        disabled={isVoting}
        aria-label="Downvote"
        className={`p-1 rounded transition-colors disabled:opacity-50 ${
          userVote === -1
            ? 'text-red-500'
            : 'text-gray-400 hover:text-red-400'
        }`}
      >
        <ChevronDown size={18} />
      </button>
    </div>
  );
};

export default VoteButtons;
