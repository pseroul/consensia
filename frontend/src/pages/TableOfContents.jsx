import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, BookOpen, ChevronRight, Download, Loader2, X, RotateCcw } from 'lucide-react';
import { getTocStructure, updateTocStructure, getIdeas, getBookImpactComments } from '../services/api';
import { useBook } from '../contexts/BookContext';

/**
 * Modal component for displaying full content of TOC items
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
      <div className="bg-white rounded-2xl p-6 w-full max-w-2xl shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto">
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
 * Recursive component to render hierarchical table of contents structure
 * @param {Object} props - Component props
 * @param {Object} props.item - Current TOC item to render
 * @param {number} props.level - Nesting level for indentation
 * @param {Function} props.onShowFullContent - Callback to show full content
 * @returns {JSX.Element} Rendered TOC item
 */
const TocItem = ({ item, level = 1, onShowFullContent, allCollapsed, scoreMap = {} }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  
  const hasChildren = item.children && item.children.length > 0;
  
  // Override expanded state based on parent collapse all state
  const isItemExpanded = item.type === 'heading' && hasChildren ? 
    (isExpanded && !allCollapsed) : 
    isExpanded;
  
  if (item.type === 'heading') {
    return (
      <div className="border-b border-gray-100 last:border-0">
        <div 
          className="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 transition-colors group cursor-pointer"
          onClick={() => setIsExpanded(!isExpanded)}
          role="button"
          tabIndex={0}
          aria-expanded={isItemExpanded}
          aria-label={`Toggle ${item.title} section`}
        >
          <div className="flex items-center gap-4">
            <span className="text-sm font-mono text-gray-400 w-6">
              {String(level).padStart(2, '0')}
            </span>
            <div>
              <span className="text-lg font-medium text-gray-800 group-hover:text-blue-700 transition-colors">
                {item.title}
              </span>
              {item.originality && (
                <span className="text-xs text-gray-500 ml-2 block">
                  Originality: {item.originality}
                </span>
              )}
              {hasChildren && (
                <span className="text-xs text-gray-500 ml-2">
                  ({item.children.length} items)
                </span>
              )}
            </div>
          </div>
          {hasChildren && (
            <ChevronRight 
              size={18} 
              className={`text-gray-300 group-hover:text-blue-400 transition-transform ${
                isItemExpanded ? 'rotate-90' : ''
              }`} 
              aria-hidden="true"
            />
          )}
        </div>
        {hasChildren && isItemExpanded && (
          <div className="ml-8 pl-4 border-l border-gray-200">
            {item.children.map((child, index) => (
              <TocItem
                key={child.id || index}
                item={child}
                level={level + 1}
                onShowFullContent={onShowFullContent}
                allCollapsed={allCollapsed}
                scoreMap={scoreMap}
              />
            ))}
          </div>
        )}
      </div>
    );
  } else {
    // Display idea item
    const score = scoreMap[item.title] ?? 0;
    return (
      <div
        className="flex items-center justify-between p-4 rounded-lg hover:bg-gray-50 transition-colors group cursor-pointer border-b border-gray-50 last:border-0"
        onClick={() => onShowFullContent(item.title, item.text)}
        role="button"
        tabIndex={0}
        aria-label={`View details for ${item.title}`}
      >
        <div className="flex items-center gap-4">
          <span className="text-sm font-mono text-gray-400 w-6">
            {String(level).padStart(2, '0')}
          </span>
          <div>
            <span className="text-lg font-medium text-gray-800 group-hover:text-blue-700 transition-colors">
              {item.title}
            </span>
            {item.text && (
              <p className="text-sm text-gray-600 mt-1 max-w-md line-clamp-2">
                {item.text}
              </p>
            )}
            <span className="text-xs text-gray-500 mt-1 block">
              Originality: {item.originality}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            data-testid="popularity-score"
            className="text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-600"
            aria-label={`Popularity score: ${score}`}
          >
            {score > 0 ? `+${score}` : score}
          </span>
          <ChevronRight size={18} className="text-gray-300 group-hover:text-blue-400" aria-hidden="true" />
        </div>
      </div>
    );
  }
};

/**
 * Table of Contents Component - Displays hierarchical structure of content
 * 
 * This component provides:
 * - Hierarchical navigation of content sections
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
/**
 * Recursively filter a TOC tree to only include leaf ideas whose titles are in allowedTitles.
 * Headings with no remaining children are dropped.
 */
const filterTocByTitles = (items, allowedTitles) =>
  items.reduce((acc, item) => {
    if (item.type === 'heading') {
      const children = filterTocByTitles(item.children ?? [], allowedTitles);
      if (children.length > 0) acc.push({ ...item, children });
    } else if (allowedTitles.has(item.title)) {
      acc.push(item);
    }
    return acc;
  }, []);

/**
 * Recursively convert a TOC tree to a markdown string.
 * Top-level items use `#`, their children `##`, etc.
 * scoreMap and tagsMap enrich idea nodes with vote count and tags.
 */
const tocToMarkdown = (items, depth = 1, scoreMap = {}, tagsMap = {}, commentsMap = {}) => {
  const prefix = '#'.repeat(depth);
  return items.reduce((md, item) => {
    if (item.type === 'heading') {
      md += `${prefix} ${item.title}\n\n`;
      if (item.children?.length) {
        md += tocToMarkdown(item.children, depth + 1, scoreMap, tagsMap, commentsMap);
      }
    } else {
      md += `${prefix} ${item.title}\n\n`;
      if (item.text) md += `${item.text}\n\n`;
      const tags = tagsMap[item.title];
      if (tags) md += `**Tags:** ${tags}\n\n`;
      const score = scoreMap[item.title] ?? 0;
      md += `**Votes:** ${score > 0 ? `+${score}` : score}\n\n`;
      const comments = commentsMap[item.title];
      if (comments?.length) {
        md += `**Impacts:**\n`;
        comments.forEach((c) => {
          md += `- ${c.username} : ${c.content}\n`;
        });
        md += '\n';
      }
    }
    return md;
  }, '');
};

const TableOfContents = () => {
  const { selectedBook } = useBook() ?? {};

  // State management for component data
  const [tocStructure, setTocStructure] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [modalContent, setModalContent] = useState({ title: '', text: '' });
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [allCollapsed, setAllCollapsed] = useState(false);
  const [bookIdeas, setBookIdeas] = useState(null);
  const [scoreMap, setScoreMap] = useState({});
  const [tagsMap, setTagsMap] = useState({});
  const [commentsMap, setCommentsMap] = useState({});

  // Fetch ideas to build score map and optionally filter TOC by selected book
  useEffect(() => {
    getIdeas()
      .then((res) => {
        const scores = {};
        const tags = {};
        res.data.forEach((idea) => {
          scores[idea.title] = idea.score ?? 0;
          if (idea.tags) tags[idea.title] = idea.tags.replace(/;/g, ', ');
        });
        setScoreMap(scores);
        setTagsMap(tags);
        if (selectedBook) {
          const titles = new Set(
            res.data
              .filter((idea) => idea.book_id === selectedBook.id)
              .map((idea) => idea.title)
          );
          setBookIdeas(titles);
        } else {
          setBookIdeas(null);
        }
      })
      .catch(() => {
        setBookIdeas(null);
        setScoreMap({});
        setTagsMap({});
      });

    if (selectedBook) {
      getBookImpactComments(selectedBook.id)
        .then((res) => {
          const cm = {};
          res.data.forEach((c) => {
            if (!cm[c.idea_title]) cm[c.idea_title] = [];
            cm[c.idea_title].push(c);
          });
          setCommentsMap(cm);
        })
        .catch(() => setCommentsMap({}));
    } else {
      setCommentsMap({});
    }
  }, [selectedBook]);

  const visibleToc = bookIdeas ? filterTocByTitles(tocStructure, bookIdeas) : tocStructure;

  /**
   * Fetch the table of contents structure from the API
   * @async
   * @returns {Promise<void>}
   */
  const fetchTocStructure = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await getTocStructure();
      setTocStructure(response.data);
    } catch (err) {
      console.error('Error fetching TOC structure:', err);
      setError('Failed to load table of contents. Please try again.');
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
   * Refresh the table of contents structure
   * @async
   * @returns {Promise<void>}
   */
  const refreshTocStructure = async () => {
    try {
      setIsRefreshing(true);
      setError(null);
      
      // First update the TOC structure
      await updateTocStructure();
      
      // Then fetch the updated structure
      const response = await getTocStructure();
      setTocStructure(response.data);
    } catch (err) {
      console.error('Error refreshing TOC structure:', err);
      setError('Failed to refresh table of contents. Please try again.');
    } finally {
      setIsRefreshing(false);
    }
  };

  // Load TOC structure when component mounts
  useEffect(() => {
    fetchTocStructure();
  }, []);

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
   * Export the visible TOC as a markdown file.
   * Filename: <YYYYMMDD-HHmm>_<book-title>.md
   */
  const exportToMarkdown = () => {
    const pad = (n) => String(n).padStart(2, '0');
    const now = new Date();
    const dateStr = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
    const bookSlug = (selectedBook?.title || 'toc').replace(/\s+/g, '_');
    const filename = `${dateStr}_${bookSlug}.md`;

    const markdown = tocToMarkdown(visibleToc, 1, scoreMap, tagsMap, commentsMap);
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
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
            <h1 className="text-3xl font-bold text-gray-900">Table of contents</h1>
            <p className="text-gray-500 italic">{visibleToc.length} sections</p>
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
              onClick={refreshTocStructure}
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
            <button
              onClick={exportToMarkdown}
              disabled={visibleToc.length === 0}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50"
              aria-label="Export as Markdown"
            >
              <Download size={18} />
              <span className="text-sm font-medium">Export MD</span>
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
            {visibleToc.length > 0 ? (
              visibleToc.map((item, index) => (
                <TocItem
                  key={item.id || index}
                  item={item}
                  level={1}
                  onShowFullContent={handleShowFullContent}
                  allCollapsed={allCollapsed}
                  scoreMap={scoreMap}
                />
              ))
            ) : (
              <p className="text-center text-gray-400 py-10">No content available at this time.</p>
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
    </div>
  );
};

export default TableOfContents;