import React, { useState, useEffect } from 'react';
import { Trash2, Loader2 } from 'lucide-react';
import { getImpactComments, createImpactComment, deleteImpactComment } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const ImpactComments = ({ ideaId }) => {
  const { user } = useAuth();
  const [comments, setComments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newContent, setNewContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    getImpactComments(ideaId)
      .then((res) => {
        if (!cancelled) setComments(res.data);
      })
      .catch(() => {
        if (!cancelled) setComments([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => { cancelled = true; };
  }, [ideaId]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newContent.trim()) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await createImpactComment(ideaId, newContent.trim());
      setComments((prev) => [...prev, res.data]);
      setNewContent('');
    } catch (err) {
      if (err.response?.status === 403) {
        setError("Vous n'avez pas accès à ce livre.");
      } else {
        setError("Une erreur est survenue.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (commentId) => {
    try {
      await deleteImpactComment(commentId);
      setComments((prev) => prev.filter((c) => c.id !== commentId));
    } catch {
      // silent — keep comment in list if delete fails
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-2">
        <Loader2 className="animate-spin text-gray-400" size={18} />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {comments.length === 0 && (
        <p className="text-xs text-gray-400 italic">Aucun impact pour l&apos;instant.</p>
      )}
      {comments.map((comment) => (
        <div key={comment.id} className="flex items-start gap-2 bg-gray-50 rounded-lg p-2">
          <div className="flex-1 min-w-0">
            <span className="text-xs font-semibold text-gray-600">{comment.username}</span>
            <span className="text-xs text-gray-400 ml-2">{comment.created_at}</span>
            <p className="text-sm text-gray-700 mt-0.5 break-words">{comment.content}</p>
          </div>
          {comment.user_email === user?.email && (
            <button
              type="button"
              onClick={() => handleDelete(comment.id)}
              aria-label="Supprimer ce commentaire"
              className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0 mt-0.5"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      ))}

      <form onSubmit={handleAdd} className="mt-2 space-y-2">
        <textarea
          rows={2}
          className="w-full border border-gray-200 p-2 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-gray-50 resize-none text-black"
          placeholder="Ajouter un impact..."
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
        />
        {error && <p className="text-xs text-red-500">{error}</p>}
        <button
          type="submit"
          disabled={isSubmitting || !newContent.trim()}
          className="w-full py-1.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? (
            <span className="flex items-center justify-center gap-1">
              <Loader2 className="animate-spin" size={14} />
              Envoi...
            </span>
          ) : (
            'Ajouter un impact'
          )}
        </button>
      </form>
    </div>
  );
};

export default ImpactComments;
