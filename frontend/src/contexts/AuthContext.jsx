import React, { createContext, useContext, useState } from 'react';

/**
 * Decode the payload of a JWT without cryptographic verification.
 * Used only to read claims (email, is_admin) for UI decisions.
 * The server still validates the signature on every request.
 */
function decodeToken(token) {
  try {
    const payload = token.split('.')[1];
    return JSON.parse(atob(payload));
  } catch {
    return null;
  }
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // Lazy initializer: hydrate from localStorage synchronously on first render
  const [user, setUser] = useState(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return null;
    const payload = decodeToken(token);
    return payload ? { email: payload.sub, is_admin: !!payload.is_admin } : null;
  });

  /** Store both tokens and decode user info from the access token. */
  function login(accessToken, refreshToken) {
    localStorage.setItem('access_token', accessToken);
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken);
    }
    const payload = decodeToken(accessToken);
    if (payload) {
      setUser({ email: payload.sub, is_admin: !!payload.is_admin });
    }
  }

  /** Clear all tokens and reset user state. */
  function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('isAuthenticated');
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
