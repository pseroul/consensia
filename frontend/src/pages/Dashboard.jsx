import React, { useState, useEffect } from 'react';
import { Plus, Search, Trash2, Edit3, Loader2, Lightbulb } from 'lucide-react';
import { getIdeas, getUserIdeas, createIdea, deleteIdea, updateIdea, getSimilarIdeas } from '../services/api';
import IdeaModal from '../components/IdeaModal';
import VoteButtons from '../components/VoteButtons';
import { useBook } from '../contexts/BookContext';

/**
 * Dashboard Component - Main page for managing ideas
 * 
 * This component provides a clean interface for:
 * - Viewing all ideas in a responsive grid
 * - Searching ideas by name or description
 * - Finding similar ideas based on search terms
 * - Creating new ideas
 * - Editing existing ideas
 * - Deleting ideas
 * 
 * Features:
 * - Responsive design for all screen sizes
 * - Loading states and error handling
 * - Tag display for ideas
 * - Modal-based forms for idea creation/editing
 * - Similar ideas search functionality
 */
const Dashboard = () => {
  const { selectedBook } = useBook() ?? {};

  // State management for all component data
  const [ideas, setIdeas] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [editingIdea, setEditingIdea] = useState(null);
  const [similarIdeas, setSimilarIdeas] = useState([]);
  const [isSearchingSimilar, setIsSearchingSimilar] = useState(false);
  const [showSimilarResults, setShowSimilarResults] = useState(false);
  const [showMyIdeasOnly, setShowMyIdeasOnly] = useState(false);

  /**
   * Fetch all ideas from the API
   * @async
   * @returns {Promise<void>}
   */
  const fetchIdeas = async () => {
    try {
      setIsLoading(true);
      const response = await (showMyIdeasOnly ? getUserIdeas() : getIdeas());
      setIdeas(response.data);
    } catch (error) {
      console.error('Error fetching ideas:', error);
      // TODO: Add proper error notification UI
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Fetch similar ideas based on search term
   * @async
   * @param {string} term - Search term to find similar ideas
   * @returns {Promise<void>}
   */
  const fetchSimilarIdeas = async (term) => {
    if (!term.trim()) return;
    
    try {
      setIsSearchingSimilar(true);
      const response = await getSimilarIdeas(term);
      setSimilarIdeas(response.data);
      setShowSimilarResults(true);
    } catch (error) {
      console.error('Error fetching similar ideas:', error);
      setSimilarIdeas([]);
      setShowSimilarResults(true);
      // TODO: Add proper error notification UI
    } finally {
      setIsSearchingSimilar(false);
    }
  };

  /**
   * Handle saving a new idea or updating an existing one
   * @async
   * @param {Object} formData - Form data containing idea details
   * @returns {Promise<void>}
   */
  const handleSaveIdea = async (formData) => {
    try {
      if (editingIdea) {
        await updateIdea(editingIdea.id, formData);
      } else {
        // The createIdea API call returns {id: newId} which we could use if needed
        await createIdea(formData);
      }

      // Refresh the ideas list after save
      fetchIdeas();
      setIsModalOpen(false);
      setEditingIdea(null);
    } catch (error) {
      console.error('Error saving idea:', error.response?.data);
      // Display error to user - could be improved with toast notifications
      const detail = error.response?.data?.detail;
      alert(`Error 422: ${JSON.stringify(detail)}`);
    }
  };

  /**
   * Handle deletion of an idea with confirmation
   * @async
   * @param {string} id - Unique identifier of the idea to delete
   * @returns {Promise<void>}
   */
  const handleDelete = async (id) => {
    if (window.confirm('Delete this idea?')) {
      try {
        // Get the idea data to send in the request body
        const ideaToDelete = ideas.find(idea => idea.id === id);
        await deleteIdea(id, ideaToDelete);
        fetchIdeas();
      } catch (error) {
        console.error('Error deleting idea:', error);
        // TODO: Add proper error notification UI
      }
    }
  };

  /**
   * Filter ideas based on search term or show similar ideas
   * @returns {Array} Filtered array of ideas
   */
  const getFilteredIdeas = () => {
    if (showSimilarResults) {
      return similarIdeas.filter(
        idea => !selectedBook || idea.book_id === selectedBook.id
      );
    }
    return ideas.filter(idea => {
      if (selectedBook && idea.book_id !== selectedBook.id) return false;
      const name = idea.title ? idea.title.toLowerCase() : "";
      const description = idea.content ? idea.content.toLowerCase() : "";
      const tags = idea.tags ? idea.tags.toLowerCase() : "";
      const search = searchTerm.toLowerCase();
      return name.includes(search) || description.includes(search) || tags.includes(search);
    });
  };

  // Load ideas when component mounts or when filter changes
  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchIdeas identity changes on every render; showMyIdeasOnly is the real trigger
  useEffect(() => { fetchIdeas(); }, [showMyIdeasOnly]);

  // Get filtered ideas for display
  const filteredIdeas = getFilteredIdeas();

  return (
    <div className="min-h-screen bg-gray-50 p-4 md:p-8">
      {/* Header Section - Search and Action Buttons */}
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row gap-4 justify-between items-center mb-8">
        <div className="flex flex-col md:flex-row gap-4 items-start md:items-center">
          <h1 className="text-2xl font-bold text-gray-800">Ideas</h1>
          {/* Toggle for filtering ideas */}
          <div className="flex items-center bg-gray-100 rounded-full p-1 text-sm shadow-inner">
            <input
              type="radio"
              id="allIdeas"
              name="ideaFilter"
              checked={!showMyIdeasOnly}
              onChange={() => setShowMyIdeasOnly(false)}
              className="sr-only"
            />
            <label
              htmlFor="allIdeas"
              className={`px-4 py-1.5 rounded-full font-medium cursor-pointer transition-all duration-200 ${
                !showMyIdeasOnly
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              All Ideas
            </label>
            <input
              type="radio"
              id="myIdeas"
              name="ideaFilter"
              checked={showMyIdeasOnly}
              onChange={() => setShowMyIdeasOnly(true)}
              className="sr-only"
            />
            <label
              htmlFor="myIdeas"
              className={`px-4 py-1.5 rounded-full font-medium cursor-pointer transition-all duration-200 ${
                showMyIdeasOnly
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              My Ideas
            </label>
          </div>
        </div>

        <div className="flex w-full md:w-auto gap-2">
          {/* Search Input */}
          <div className="relative flex-grow">
            <Search className="absolute left-3 top-2.5 text-gray-400" size={18} />
            <input 
              type="text"
              placeholder="Search..."
              className="pl-10 pr-4 py-2 border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                // Reset similar results when typing in search
                if (showSimilarResults) {
                  setShowSimilarResults(false);
                }
              }}
            />
          </div>
          
          {/* Similar Ideas Button */}
          <button
            onClick={() => fetchSimilarIdeas(searchTerm)}
            disabled={!searchTerm.trim() || isSearchingSimilar}
            aria-label="Similar"
            className="bg-purple-600 hover:bg-purple-700 disabled:bg-purple-300 text-white p-2 rounded-lg flex items-center gap-2 transition-colors"
          >
            {isSearchingSimilar ? (
              <Loader2 className="animate-spin" size={20} />
            ) : (
              <Lightbulb size={20} />
            )}
            <span className="hidden md:inline">Similar</span>
          </button>
          
          {/* New Idea Button */}
          <button
            onClick={() => {
              setEditingIdea(null);
              setIsModalOpen(true);
            }}
            disabled={!selectedBook}
            title={!selectedBook ? 'Select a book first' : undefined}
            aria-label="New idea"
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white p-2 rounded-lg flex items-center gap-2 transition-colors"
          >
            <Plus size={20} />
            <span className="hidden md:inline">New</span>
          </button>
        </div>
      </div>

      {/* Ideas Grid */}
      {isLoading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="animate-spin text-blue-600" size={48} />
        </div>
      ) : (
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredIdeas.map((idea) => (
            <div key={idea.id} className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
              {/* Idea Header with Actions */}
              <div className="flex justify-between items-start mb-4">
                <h3 className="font-semibold text-lg text-gray-900">{idea.title}</h3>
                <div className="flex gap-2">
                  <button 
                    onClick={() => { 
                      setEditingIdea(idea); 
                      setIsModalOpen(true); 
                    }} 
                    className="text-gray-400 hover:text-blue-600 transition-colors"
                    aria-label="Edit idea"
                  >
                    <Edit3 size={18} />
                  </button>
                  <button 
                    onClick={() => handleDelete(idea.id)} 
                    className="text-gray-400 hover:text-red-500 transition-colors"
                    aria-label="Delete idea"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
              
              {/* Idea Description */}
              <p className="text-gray-600 text-sm leading-relaxed">{idea.content}</p>
              
              {/* Tags Display */}
              {idea.tags && typeof idea.tags === 'string' && idea.tags.trim().length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2 p-2 rounded">
                  <span className="text-xs font-medium text-green-700">TAGS:</span>
                  {idea.tags.split(';').map((tag, index) => {
                    const trimmedTag = tag.trim();
                    return trimmedTag ? (
                      <span
                        key={index}
                        className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full"
                      >
                        {trimmedTag}
                      </span>
                    ) : null;
                  })}
                </div>
              )}

              {/* Vote Buttons */}
              <VoteButtons ideaId={idea.id} />
            </div>
          ))}
        </div>
      )}

      {/* Idea Creation/Edit Modal */}
      <IdeaModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSave={handleSaveIdea}
        initialData={editingIdea}
        bookId={selectedBook?.id}
      />
    </div>
  );
};

export default Dashboard;