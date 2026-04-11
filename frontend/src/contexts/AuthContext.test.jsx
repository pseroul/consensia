/**
 * AuthContext.test.jsx
 * Unit tests for AuthContext — login, logout, JWT decoding, hydration.
 */

import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

import { AuthProvider, useAuth } from './AuthContext';

// ---------------------------------------------------------------------------
// Helper: minimal component that exposes auth state
// ---------------------------------------------------------------------------

function Consumer() {
  const { user, isAuthenticated } = useAuth();
  return (
    <div>
      <span data-testid="authenticated">{String(isAuthenticated)}</span>
      <span data-testid="email">{user?.email ?? 'none'}</span>
      <span data-testid="is_admin">{user ? String(user.is_admin) : 'none'}</span>
    </div>
  );
}

function LoginConsumer({ refreshToken } = {}) {
  const { login } = useAuth();
  return (
    <button onClick={() => login('TOKEN', refreshToken)} data-testid="login-btn">
      Login
    </button>
  );
}

function LogoutConsumer() {
  const { logout } = useAuth();
  return (
    <button onClick={logout} data-testid="logout-btn">
      Logout
    </button>
  );
}

// A real JWT payload for tests (header.payload.signature — signature not verified client-side)
// sub=test@example.com, is_admin=false
const NON_ADMIN_TOKEN =
  'eyJhbGciOiJIUzI1NiJ9.' +
  btoa(JSON.stringify({ sub: 'test@example.com', is_admin: false, exp: 9999999999 })).replace(/=/g, '') +
  '.fakesig';

// sub=admin@example.com, is_admin=true
const ADMIN_TOKEN =
  'eyJhbGciOiJIUzI1NiJ9.' +
  btoa(JSON.stringify({ sub: 'admin@example.com', is_admin: true, exp: 9999999999 })).replace(/=/g, '') +
  '.fakesig';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuthContext — initial state (no localStorage)', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('isAuthenticated is false when no token exists', () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    expect(screen.getByTestId('authenticated').textContent).toBe('false');
  });

  it('user is null when no token exists', () => {
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    expect(screen.getByTestId('email').textContent).toBe('none');
  });
});

describe('AuthContext — hydration from localStorage', () => {
  afterEach(() => localStorage.clear());

  it('hydrates user from a stored non-admin token', () => {
    localStorage.setItem('access_token', NON_ADMIN_TOKEN);
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    expect(screen.getByTestId('authenticated').textContent).toBe('true');
    expect(screen.getByTestId('email').textContent).toBe('test@example.com');
    expect(screen.getByTestId('is_admin').textContent).toBe('false');
  });

  it('hydrates is_admin=true from a stored admin token', () => {
    localStorage.setItem('access_token', ADMIN_TOKEN);
    render(
      <AuthProvider>
        <Consumer />
      </AuthProvider>
    );
    expect(screen.getByTestId('is_admin').textContent).toBe('true');
  });
});

describe('AuthContext — login()', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => localStorage.clear());

  it('stores access_token in localStorage', async () => {
    render(
      <AuthProvider>
        <LoginConsumer />
        <Consumer />
      </AuthProvider>
    );
    await act(async () => {
      screen.getByTestId('login-btn').click();
    });
    expect(localStorage.getItem('access_token')).toBe('TOKEN');
  });

  it('stores refresh_token in localStorage when provided', async () => {
    render(
      <AuthProvider>
        <LoginConsumer refreshToken="RTOKEN" />
        <Consumer />
      </AuthProvider>
    );
    await act(async () => {
      screen.getByTestId('login-btn').click();
    });
    expect(localStorage.getItem('refresh_token')).toBe('RTOKEN');
  });

  it('does not write refresh_token when not provided', async () => {
    render(
      <AuthProvider>
        <LoginConsumer />
        <Consumer />
      </AuthProvider>
    );
    await act(async () => {
      screen.getByTestId('login-btn').click();
    });
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });
});

describe('AuthContext — logout()', () => {
  afterEach(() => localStorage.clear());

  it('clears access_token and sets isAuthenticated to false', async () => {
    localStorage.setItem('access_token', NON_ADMIN_TOKEN);
    render(
      <AuthProvider>
        <LogoutConsumer />
        <Consumer />
      </AuthProvider>
    );
    expect(screen.getByTestId('authenticated').textContent).toBe('true');

    await act(async () => {
      screen.getByTestId('logout-btn').click();
    });

    expect(screen.getByTestId('authenticated').textContent).toBe('false');
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('also clears refresh_token on logout', async () => {
    localStorage.setItem('access_token', NON_ADMIN_TOKEN);
    localStorage.setItem('refresh_token', 'some-refresh-token');
    render(
      <AuthProvider>
        <LogoutConsumer />
        <Consumer />
      </AuthProvider>
    );
    await act(async () => {
      screen.getByTestId('logout-btn').click();
    });
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });
});
