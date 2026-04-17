import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, BookOpen, ChevronRight, Loader2, X, RotateCcw, Trash2 } from 'lucide-react';
import { getTags, getIdeasFromTags, getIdeas, deleteTag } from '../services/api';
import { useBook } from '../contexts/BookContext';

/**
 * Modal component for displaying full content of tags and ideas
 * @param {Object} props - Component props
 * @param {boolean} props.isOpen - Whether modal is visible
 * @param {Function} props.onClose - Function to close modal
 * @param {string} props.content - Full content to display
 * @param {string} props.title - Title of the content
 * @returns {JSX.Element|null} Modal component or null
 */
const FullContentModal = ({ isOpen, onClose, content, title }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black bg-opacity-70">
      <div role="dialog" aria-modal="true" className="bg-white rounded-2xl p-6 w-full max-w-2xl shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-xl font-bold text-gray-900">{title}</h2>
          <button
            onClick={onClose}
            type="button"
            className="p-1 hover:bg-gray-100 rounded-full transition-colors"
            aria-label="Close modal"
          >
            <X size={24} className="text-gray-400" />
          </button>
        </div>
        <div className="prose max-w-none">
          <p className="whitespace-pre-wrap text-gray-700 leading-relaxed">
            {content}
          </p>
        </div>
        <div className="mt-6 flex justify-end">
          <button 
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            aria-label="Close"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * Modal component for deletion confirmation
 * @param {Object} props - Component props
 * @param {boolean} props.isOpen - Whether modal is visible
 * @param {Function} props.onClose - Function to close modal
 * @param {Function} props.onConfirm - Function to execute on confirmation
 * @param {string} props.itemName - Name of the item to delete
 * @returns {JSX.Element|null} Modal component or null
 */
const DeleteConfirmationModal = ({ isOpen, onClose, onConfirm, itemName }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black bg-opacity-70">
      <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-100">
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-xl font-bold text-gray-900">Confirm Deletion</h2>
          <button 
            onClick={onClose} 
            type="button" 
            className="p-1 hover:bg-gray-100 rounded-full transition-colors" 
            aria-label="Close modal"
          >
            <X size={24} className="text-gray-400" />
          </button>
        </div>
        <div className="mb-6">
          <p className="text-gray-700">
            Are you sure you want to delete the tag "{itemName}"? This action cannot be undone.
          </p>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <button 
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition-colors"
            aria-label="Cancel"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
};

/**
 * Recursive component to render hierarchical tags and ideas structure
 * @param {Object} props - Component props
 * @param {Object} props.item - Current tag or idea to render
 * @param {number} props.level - Nesting level for indentation
 * @param {Function} props.onShowFullContent - Callback to show full content
 * @returns {JSX.Element} Rendered tag or idea
 */
const TagItem = ({ item, level = 1, onShowFullContent, allCollapsed, onDeleteTag }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  
  const hasIdeas = item.ideas && item.ideas.length > 0;
  const isTag = hasIdeas;
  
  // Override expanded state based on parent collapse all state
  const isItemExpanded = hasIdeas ? (isExpanded && !allCollapsed) : isExpanded;

  if (isTag) {
    return (
      <div className="border-b border-gray-100 last:border-0">
        <div 
          className="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 transition-colors group cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
          role="button"
          tabIndex={0}
          aria-expanded={isItemExpanded}
          aria-label={`Toggle ${item.name} section`}
        >
          <div className="flex items-center gap-4">
            <span className="text-sm font-mono text-gray-400 w-6">
              {String(level).padStart(2, '0')}
            </span>
            <div>
              <span className="text-lg font-medium text-gray-800 group-hover:text-blue-700 transition-colors">
                {item.name}
              </span>
              {hasIdeas && (
                <span className="text-xs text-gray-500 ml-2">
                  ({item.ideas.length} ideas)
                </span>
              )}
            </div>
          </div>
          {hasIdeas && (
            <ChevronRight 
              size={18} 
              className={`text-gray-300 group-hover:text-blue-400 transition-transform ${
                isItemExpanded ? 'rotate-90' : ''
              }`} 
              aria-hidden="true"
            />
          )}
        </div>
        {hasIdeas && isItemExpanded && (
          <div className="ml-8 pl-4 border-l border-gray-200">
            {item.ideas.map((idea, index) => (
              <TagItem 
                key={idea.id || index} 
                item={idea} 
                level={level + 1} 
                onShowFullContent={onShowFullContent}
                allCollapsed={allCollapsed}
                onDeleteTag={onDeleteTag}
              />
            ))}
          </div>
        )}
      </div>
    );
  } else {
    // Display idea item - only show modal for actual ideas, not tags without ideas
    // Check if this is an actual idea (has a description) or just a tag without ideas
    const isActualIdea = item.description && item.description !== '';
    
    if (isActualIdea) {
      return (
        <div
          className="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 transition-colors group cursor-pointer border-b border-gray-50 last:border-0"
          onClick={() => onShowFullContent(item.name, item.description || '')}
          role="button"
          tabIndex={0}
          aria-label={`View details for ${item.name}`}
        >
          <div className="flex items-center gap-4">
            <span className="text-sm font-mono text-gray-400 w-6">
              {String(level).padStart(2, '0')}
            </span>
            <div>
              <span className="text-lg font-medium text-gray-800 group-hover:text-blue-700 transition-colors">
                {item.name}
              </span>
              {item.description && (
                <p className="text-sm text-gray-600 mt-1 max-w-md line-clamp-2">
                  {item.description}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span
              data-testid="popularity-score"
              className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-600"
              aria-label={`Popularity score: ${item.score}`}
            >
              {item.score > 0 ? `+${item.score}` : item.score}
            </span>
            <ChevronRight size={18} className="text-gray-300 group-hover:text-blue-400" aria-hidden="true" />
          </div>
        </div>
      );
    } else {
      // This is a tag without ideas - display it with delete button
      return (
        <div 
          className="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 transition-colors group cursor-pointer border-b border-gray-50 last:border-0"
          role="button"
          tabIndex={0}
          aria-label={item.name}
        >
          <div className="flex items-center gap-4">
            <span className="text-sm font-mono text-gray-400 w-6">
              {String(level).padStart(2, '0')}
            </span>
            <div>
              <span className="text-lg font-medium text-gray-800 group-hover:text-blue-700 transition-colors">
                {item.name}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteTag(item.name);
              }}
              className="p-1 hover:bg-red-50 rounded-full transition-colors"
              aria-label={`Delete tag ${item.name}`}
            >
              <Trash2 size={18} className="text-red-500" />
            </button>
            <ChevronRight size={18} className="text-gray-300 group-hover:text-blue-400" aria-hidden="true" />
          </div>
        </div>
      );
    }
  }
};

/**
 * Tags and Ideas Page Component - Displays hierarchical structure of tags and their associated ideas
 *
 * This component provides:
 * - Hierarchical navigation of tags and ideas
 * - Ability to view full content in a modal
 * - Refresh functionality to update content structure
 * - Responsive design for all screen sizes
 * - Accessible UI components
 *
 * Features:
 * - Collapsible sections
 * - Loading states
 * - Error handling
 * - Full content preview
 * - Content refresh capability
 */
const TagsIdeasPage = () => {
  const { selectedBook } = useBook() ?? {};

  // State management for component data
  const [tags, setTags] = useState([]);
  const [untaggedIdeas, setUntaggedIdeas] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [modalContent, setModalContent] = useState({ title: '', text: '' });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [allCollapsed, setAllCollapsed] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [tagToDelete, setTagToDelete] = useState('');

  /**
   * Fetch tags and their associated ideas from the API
   * @async
   * @returns {Promise<void>}
   */
  const fetchTagsAndIdeas = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const tagsResponse = await getTags(selectedBook?.id ?? null);
      const tagsData = tagsResponse.data;

      const tagsWithIdeas = await Promise.all(
        tagsData.map(async (tag) => {
          const ideasResponse = await getIdeasFromTags(tag.name, selectedBook?.id ?? null);
          const ideasData = ideasResponse.data;
          return {
            name: tag.name,
            ideas: ideasData.map(idea => ({
              id: idea.id,
              name: idea.title || 'Untitled Idea',
              description: idea.content || '',
              score: idea.score ?? 0,
            })),
          };
        })
      );

      setTags(tagsWithIdeas);
      
      // Fetch ideas (filtered by book if selected) to find untagged ones
      const allIdeasResponse = await getIdeas(selectedBook?.id ?? null);
      const allIdeasData = allIdeasResponse.data;

      // Find ideas that don't belong to any tag
      const taggedIdeaIds = new Set();
      tagsWithIdeas.forEach(tag => {
        tag.ideas.forEach(idea => {
          if (idea.id) taggedIdeaIds.add(idea.id);
        });
      });

      const untagged = allIdeasData
        .filter(idea => !taggedIdeaIds.has(idea.id))
        .map(idea => ({
        id: idea.id,
        name: idea.title || 'Untitled Idea',
        description: idea.content || '',
        score: idea.score ?? 0,
      }));

      setUntaggedIdeas(untagged);
    } catch (err) {
      console.error('Error fetching tags and ideas:', err);
      setError('Failed to load tags and ideas. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle showing full content in modal
   * @param {string} title - Title of the content
   * @param {string} text - Full text content
   * @returns {void}
   */
  const handleShowFullContent = (title, text) => {
    setModalContent({ title, text });
    setShowModal(true);
  };

  /**
   * Close the modal and reset content
   * @returns {void}
   */
  const handleCloseModal = () => {
    setShowModal(false);
    setModalContent({ title: '', text: '' });
  };

  /**
   * Refresh the tags and ideas structure
   * @async
   * @returns {Promise<void>}
   */
  const refreshTagsAndIdeas = async () => {
    try {
      setIsRefreshing(true);
      setError(null);
      await fetchTagsAndIdeas();
    } catch (err) {
      console.error('Error refreshing tags and ideas:', err);
      setError('Failed to refresh tags and ideas. Please try again.');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Load tags and ideas when component mounts or selected book changes
  useEffect(() => {
    fetchTagsAndIdeas();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBook]);

  /**
   * Collapse all sections
   * @returns {void}
   */
  const collapseAllSections = () => {
    setAllCollapsed(true);
  };

  /**
   * Expand all sections
   * @returns {void}
   */
  const expandAllSections = () => {
    setAllCollapsed(false);
  };

  /**
   * Handle tag deletion
   * @param {string} tagName - Name of the tag to delete
   * @returns {void}
   */
  const handleDeleteTag = (tagName) => {
    setTagToDelete(tagName);
    setShowDeleteModal(true);
  };

  /**
   * Confirm tag deletion and call API
   * @async
   * @returns {Promise<void>}
   */
  const confirmDeleteTag = async () => {
    try {
      setError(null);
      await deleteTag(tagToDelete);
      // Refresh the tags list after deletion
      await fetchTagsAndIdeas();
      setShowDeleteModal(false);
      setTagToDelete('');
    } catch (err) {
      console.error('Error deleting tag:', err);
      setError('Failed to delete tag. Please try again.');
    }
  };

  /**
   * Close delete confirmation modal
   * @returns {void}
   */
  const closeDeleteModal = () => {
    setShowDeleteModal(false);
    setTagToDelete('');
  };

  return (
    <div className="min-h-screen bg-white p-4 md:p-12">
      <div className="max-w-3xl mx-auto">
        
        {/* Navigation back to dashboard */}
        <Link 
          to="/dashboard" 
          className="flex items-center gap-2 text-gray-500 hover:text-blue-600 transition-colors mb-8 group"
          aria-label="Back to dashboard"
        >
          <ArrowLeft size={20} className="group-hover:-translate-x-1 transition-transform" />
          <span>Back to Dashboard</span>
        </Link>

        {/* Page header */}
        <div className="flex items-center gap-4 mb-12 border-b border-gray-100 pb-6">
          <div className="bg-blue-50 p-3 rounded-full text-blue-600">
            <BookOpen size={28} />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Tags and Ideas</h1>
            <p className="text-gray-500 italic">{tags.length} tags</p>
          </div>
          <div className="ml-auto flex gap-2">
            <button
              onClick={collapseAllSections}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              aria-label="Collapse all sections"
            >
              <ChevronRight size={18} className="" />
              <span className="text-sm font-medium">Collapse All</span>
            </button>
            <button
              onClick={expandAllSections}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              aria-label="Expand all sections"
            >
              <ChevronRight size={18} className="rotate-90" />
              <span className="text-sm font-medium">Expand All</span>
            </button>
            <button
              onClick={refreshTagsAndIdeas}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50"
              aria-label={isRefreshing ? "Refreshing..." : "Refresh content"}
            >
              {isRefreshing ? (
                <Loader2 className="animate-spin" size={18} />
              ) : (
                <RotateCcw size={18} />
              )}
              <span className="text-sm font-medium">Refresh</span>
            </button>
          </div>
        </div>

        {/* Content display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin text-blue-600" size={32} />
          </div>
        ) : (
          <div className="space-y-1">
            {tags.length > 0 ? (
              tags.map((tag, index) => (
                <TagItem 
                  key={tag.name || index} 
                  item={tag} 
                  level={1} 
                  onShowFullContent={handleShowFullContent}
                  allCollapsed={allCollapsed}
                  onDeleteTag={handleDeleteTag}
                />
              ))
            ) : (
              <p className="text-center text-gray-400 py-10">No tags available at this time.</p>
            )}
            
            {/* Untagged ideas section */}
            {untaggedIdeas.length > 0 && (
              <div className="border-t border-gray-200 mt-8 pt-4">
                <div className="flex items-center gap-4 p-4 bg-gray-50 rounded-lg">
                  <span className="text-sm font-mono text-gray-400 w-6">00</span>
                  <span className="text-lg font-medium text-gray-800">Untagged Ideas</span>
                  <span className="text-xs text-gray-500 ml-2">({untaggedIdeas.length} ideas)</span>
                </div>
                <div className="ml-8 pl-4 border-l border-gray-200">
                  {untaggedIdeas.map((idea, index) => (
                    <TagItem 
                      key={idea.id || index} 
                      item={idea} 
                      level={2} 
                      onShowFullContent={handleShowFullContent}
                      allCollapsed={allCollapsed}
                      onDeleteTag={handleDeleteTag}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Full Content Modal */}
      <FullContentModal 
        isOpen={showModal}
        onClose={handleCloseModal}
        content={modalContent.text}
        title={modalContent.title}
      />

      {/* Delete Confirmation Modal */}
      <DeleteConfirmationModal 
        isOpen={showDeleteModal}
        onClose={closeDeleteModal}
        onConfirm={confirmDeleteTag}
        itemName={tagToDelete}
      />
    </div>
  );
};

export default TagsIdeasPage;