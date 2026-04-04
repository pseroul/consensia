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

// Add response interceptor to handle 401 Unauthorized errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Token expired or invalid, clear authentication
      localStorage.removeItem('access_token');
      localStorage.removeItem('isAuthenticated');
      // Redirect to login page
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export const getIdeas = () => api.get('/ideas');
export const getUserIdeas = () => api.get('/user/ideas');
export const getIdeasFromTags = (tags) => api.get(`/ideas/tags/${tags}`);
export const getTocStructure = () => api.get('/toc/structure');
export const updateTocStructure = () => api.post('/toc/update');

export const getTags = () => api.get('/tags');
export const getSimilarIdeas = (idea) => api.get(`/ideas/similar/${idea}`);

export const createIdea = (idea) => api.post('/ideas', idea);
export const updateIdea = (id, idea) => api.put(`/ideas/${id}`, idea);

export const deleteIdea = (id, ideaData) => api.delete(`/ideas/${id}`, { data: ideaData });
export const deleteTag = (name) => api.delete(`/tags/${name}`);
export const verifyOtp = (credentials) => api.post('/verify-otp', credentials);
