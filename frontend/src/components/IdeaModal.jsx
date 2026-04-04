import React, { useState, useEffect } from 'react';
import { X, Tag, Loader2 } from 'lucide-react'; // Vérifie bien que 'Tag' est ici

const IdeaModal = ({ isOpen, onClose, onSave, initialData }) => {
  const [formData, setFormData] = useState({ title: '', content: '' });
  const [currentTag, setCurrentTag] = useState('');
  const [tags, setTags] = useState([]);
  const [isSaving, setIsSaving] = useState(false);

  /* eslint-disable react-hooks/set-state-in-effect -- intentional: syncs form fields when modal opens or initialData changes */
  useEffect(() => {
    if (initialData) {
      setFormData({ title: initialData.title || '', content: initialData.content || '' });
      // Handle tags - if tags is a string (semicolon-separated), split it into array
      if (initialData.tags && typeof initialData.tags === 'string') {
        setTags(initialData.tags.split(';').filter(tag => tag.trim() !== ''));
      } else if (Array.isArray(initialData.tags)) {
        setTags(initialData.tags);
      } else {
        setTags([]);
      }
    } else {
      setFormData({ title: '', content: '' });
      setTags([]);
    }
  }, [initialData, isOpen]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const addTag = (e) => {
    if (e.key === 'Enter' && currentTag.trim() !== '') {
      e.preventDefault();
      if (!tags.includes(currentTag.trim())) {
        setTags([...tags, currentTag.trim()]);
      }
      setCurrentTag('');
    }
  };

  const removeTag = (indexToRemove) => {
    setTags(tags.filter((_, index) => index !== indexToRemove));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSaving(true);
    const dataToSave = {
      title: formData.title,
      content: formData.content,
      tags: tags.length > 0 ? tags.join(';') : "" // Send as semicolon-separated string
    };

    const savePromise = onSave(dataToSave);
    if (savePromise && typeof savePromise.finally === 'function') {
      savePromise.finally(() => {
        setIsSaving(false);
      });
    } else {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div data-testid="modal-overlay" onClick={handleOverlayClick} className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black bg-opacity-70">
      <div data-testid="modal-content" role="dialog" className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-bold text-gray-900">
            {initialData ? 'Modifier l’idée' : 'Nouvelle Idée'}
          </h2>
          <button onClick={onClose} type="button" data-testid="close-button" aria-label="Close" className="p-1 hover:bg-gray-100 rounded-full transition-colors">
            <X size={24} className="text-gray-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} role="form" className="space-y-4">
          <div>
            <label htmlFor="title" className="block text-sm font-semibold text-gray-700 mb-1">Title</label>
            <input 
              id="title"
              required
              className="w-full border border-gray-200 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all bg-gray-50 text-black"
              placeholder="Artificial Intelligence"
              value={formData.title}
              onChange={(e) => setFormData({...formData, title: e.target.value})}
            />
          </div>
          
          <div>
            <label htmlFor="content" className="block text-sm font-semibold text-gray-700 mb-1">Content</label>
            <textarea 
              id="content"
              required
              rows="4"
              className="w-full border border-gray-200 p-3 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all bg-gray-50 resize-none text-black"
              placeholder="Describe your idea..."
              value={formData.content}
              onChange={(e) => setFormData({...formData, content: e.target.value})}
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">Tags (Press Enter)</label>
            <div className="flex flex-wrap gap-2 mb-2">
              {tags.map((tag, index) => (
                <span key={index} className="flex items-center gap-1 bg-blue-100 text-blue-700 px-2 py-1 rounded-lg text-sm font-medium">
                  #{tag}
                  <button type="button" onClick={() => removeTag(index)} className="hover:text-blue-900">
                    <X size={14} />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative">
              <input 
                className="w-full border border-gray-200 p-3 pl-10 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none bg-gray-50 text-black"
                placeholder="Ajouter un tag..."
                value={currentTag}
                onChange={(e) => setCurrentTag(e.target.value)}
                onKeyDown={addTag}
              />
              <Tag className="absolute left-3 top-3.5 text-gray-400" size={18} />
            </div>
          </div>

          <div className="flex gap-3 pt-4">
            <button 
              type="button"
              onClick={onClose} 
              className="flex-1 py-3 text-gray-600 font-bold hover:bg-gray-100 rounded-xl transition-colors"
            >
              Cancel
            </button>
            <button 
              type="submit"
              data-testid="submit-button"
              disabled={isSaving}
              className="flex-1 py-3 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 shadow-lg shadow-blue-200 transition-all active:scale-95 disabled:opacity-80 disabled:cursor-wait"
            >
              {isSaving ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="animate-spin" size={18} />
                  <span>Saving...</span>
                </span>
              ) : (
                initialData ? 'Update' : 'Save'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default IdeaModal;