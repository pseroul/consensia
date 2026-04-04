import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Menu, X, LogOut, Lightbulb, Home, Settings, User, Tag } from 'lucide-react';

const Navbar = ({ isOpen: controlledIsOpen = false }) => {
  const [isOpen, setIsOpen] = useState(controlledIsOpen);
  const isAuthenticated = !!localStorage.getItem('access_token');

  if (!isAuthenticated) return null;

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    window.location.href = '/';
  };

  const toggleMenu = () => setIsOpen(!isOpen);

  return (
    <nav className="bg-white border-b border-gray-200 fixed top-0 w-full z-[100] shadow-sm">
      <div className="max-w-7xl mx-auto px-4 h-16 flex justify-between items-center">
        {/* Logo / Titre */}
        <div data-testid="logo" alt="Brainiac5 Logo" className="flex items-center gap-2 font-bold text-blue-600">
          <Lightbulb size={24} />
          <span>Consensia</span>
        </div>

        {/* Bouton Menu (Burger) */}
        <button 
          onClick={toggleMenu}
          className="p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-600"
        >
          {isOpen ? <X size={28} /> : <Menu size={28} />}
        </button>
      </div>

      {/* Menu Déroulant (Dropdown) */}
      {isOpen && (
        <div className="absolute top-16 left-0 w-full bg-white border-b border-gray-200 shadow-xl animate-in slide-in-from-top duration-200">
          <div className="flex flex-col p-4 gap-2">
            <Link 
              to="/dashboard" 
              onClick={toggleMenu}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-blue-50 text-gray-700 hover:text-blue-600 font-medium transition-all"
            >
              <Home size={20} /> Dashboard
            </Link>
            
            <Link 
              to="/table-of-contents" 
              onClick={toggleMenu}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-blue-50 text-gray-700 hover:text-blue-600 font-medium transition-all"
            >
              <User size={20} /> Table of contents
            </Link>

            <Link 
              to="/tags-ideas" 
              onClick={toggleMenu}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-blue-50 text-gray-700 hover:text-blue-600 font-medium transition-all"
            >
              <Tag size={20} /> Tags & Ideas
            </Link>

            <hr className="my-2 border-gray-100" />

            <button
              data-testid="logout-icon"
              onClick={handleLogout}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-red-50 text-red-500 font-bold transition-all"
            >
              <LogOut size={20} /> Disconnect
            </button>
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;