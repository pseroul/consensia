/* eslint-disable react-refresh/only-export-components -- context files always export both provider and hook */
import React, { createContext, useContext, useState, useEffect } from 'react';
import { getBooks } from '../services/api';

const BookContext = createContext(null);

export const BookProvider = ({ children }) => {
  const [books, setBooks] = useState([]);
  const [selectedBook, setSelectedBook] = useState(null);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    getBooks()
      .then((res) => setBooks(res.data))
      .catch(() => {});
  }, []);

  return (
    <BookContext.Provider value={{ books, setBooks, selectedBook, setSelectedBook }}>
      {children}
    </BookContext.Provider>
  );
};

export const useBook = () => useContext(BookContext);
