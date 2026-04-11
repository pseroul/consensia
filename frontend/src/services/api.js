import axios from 'axios';

// Determine API URL based on environment variables
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Create axios instance with JWT token interceptor
const api = axios.create({
  baseURL: API_URL,
});

// Add request interceptor to include JWT token in Authorization header
api.interceptors.request.use(
  (config) => {
    // Get token from localStorage
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// State for queuing concurrent requests that arrive while a refresh is in flight
let isRefreshing = false;
let failedQueue = [];

function processQueue(error, token = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
}

function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  localStorage.removeItem('isAuthenticated');
  window.location.href = '/';
}

// Add response interceptor: silently refresh on 401, redirect only when refresh fails
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Non-401 errors pass through immediately
    if (!error.response || error.response.status !== 401) {
      return Promise.reject(error);
    }

    // Prevent infinite retry loop if the refresh endpoint itself returns 401
    if (originalRequest.url === '/auth/refresh') {
      clearSession();
      return Promise.reject(error);
    }

    // Queue concurrent 401 failures while a refresh is already in flight
    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        failedQueue.push({ resolve, reject });
      })
        .then((newToken) => {
          originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
          return api.request(originalRequest);
        })
        .catch((err) => Promise.reject(err));
    }

    const storedRefreshToken = localStorage.getItem('refresh_token');
    if (!storedRefreshToken) {
      // No refresh token available — force logout
      processQueue(error, null);
      clearSession();
      return Promise.reject(error);
    }

    isRefreshing = true;
    try {
      const { data } = await api.post('/auth/refresh', {
        refresh_token: storedRefreshToken,
      });
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      originalRequest.headers['Authorization'] = `Bearer ${data.access_token}`;
      processQueue(null, data.access_token);
      return api.request(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      clearSession();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export const getIdeas = (bookId = null) =>
  api.get('/ideas', bookId != null ? { params: { book_id: bookId } } : {});
export const getUserIdeas = () => api.get('/user/ideas');
export const getIdeasFromTags = (tags, bookId = null) =>
  api.get(`/ideas/tags/${tags}`, bookId != null ? { params: { book_id: bookId } } : {});
export const getTocStructure = () => api.get('/toc/structure');
export const updateTocStructure = () => api.post('/toc/update');

export const getTags = (bookId = null) =>
  api.get('/tags', bookId != null ? { params: { book_id: bookId } } : {});
export const getSimilarIdeas = (idea) => api.get(`/ideas/similar/${idea}`);

export const createIdea = (idea) => api.post('/ideas', idea);
export const updateIdea = (id, idea) => api.put(`/ideas/${id}`, idea);

export const deleteIdea = (id, ideaData) => api.delete(`/ideas/${id}`, { data: ideaData });
export const deleteTag = (name) => api.delete(`/tags/${name}`);
export const verifyOtp = (credentials) => api.post('/verify-otp', credentials);

export const getBooks = () => api.get('/books');
export const createBook = (book) => api.post('/books', book);
export const deleteBook = (id) => api.delete(`/books/${id}`);
export const getBookAuthors = (bookId) => api.get(`/books/${bookId}/authors`);
export const addBookAuthor = (bookId, userId) => api.post('/book-authors', { book_id: bookId, user_id: userId });
export const removeBookAuthor = (bookId, userId) => api.delete('/book-authors', { data: { book_id: bookId, user_id: userId } });
export const getUsers = () => api.get('/users');

export const getIdeaVotes = (id) => api.get(`/ideas/${id}/votes`);
export const castVote = (id, value) => api.post(`/ideas/${id}/vote`, { value });
export const removeVote = (id) => api.delete(`/ideas/${id}/vote`);

// Impact comments
export const getImpactComments = (ideaId) => api.get(`/ideas/${ideaId}/impact-comments`);
export const getBookImpactComments = (bookId) => api.get(`/books/${bookId}/impact-comments`);
export const createImpactComment = (ideaId, content) => api.post(`/ideas/${ideaId}/impact-comments`, { content });
export const deleteImpactComment = (commentId) => api.delete(`/impact-comments/${commentId}`);

// Admin user-management
export const getAdminUsers = () => api.get('/admin/users');
export const createAdminUser = (data) => api.post('/admin/users', data);
export const updateAdminUser = (id, data) => api.put(`/admin/users/${id}`, data);
export const deleteAdminUser = (id) => api.delete(`/admin/users/${id}`);
