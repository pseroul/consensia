import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

// Importation des pages
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import TableOfContents from './pages/TableOfContents';
import TagsIdeasPage from './pages/TagsIdeasPage';
import Navbar from './components/Navbar';
import BooksPage from './pages/BooksPage';
import { BookProvider } from './contexts/BookContext';

const ProtectedRoute = ({ children }) => {
  // const auth = true; // Simulation for debug
  const auth = localStorage.getItem('access_token');
  return auth ? children : <Navigate to="/" />;
};

function App() {
  return (
    <div className="pt-20 p-4"> {/* pt-20 laisse de la place sous la Navbar */}
    <Router>
    <BookProvider>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <div className="min-h-screen bg-gray-50 text-gray-900 font-sans">
          <Routes>
            {/* Route par défaut : Connexion */}
            <Route path="/" element={<Login />} />

            {/* Routes protégées */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/table-of-contents" 
              element={
                <ProtectedRoute>
                  <TableOfContents />
                </ProtectedRoute>
              } 
            />

            <Route
              path="/tags-ideas"
              element={
                <ProtectedRoute>
                  <TagsIdeasPage />
                </ProtectedRoute>
              }
            />

            <Route
              path="/books"
              element={
                <ProtectedRoute>
                  <BooksPage />
                </ProtectedRoute>
              }
            />

            {/* Redirection si l'URL n'existe pas */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </BookProvider>
    </Router>
    </div>
  );
}

export default App;