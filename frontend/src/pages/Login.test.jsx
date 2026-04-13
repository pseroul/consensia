/**
 * Login.test.jsx
 * Unit tests for the Login page component.
 *
 * Coverage:
 * - Rendering (fields, labels, footer)
 * - OTP input validation (digits-only, max 6 chars)
 * - Form validation guards (empty email, invalid OTP)
 * - Successful authentication flow (token stored, navigate called)
 * - Failed authentication (bad status, API error)
 * - Loading state during submission
 * - Error clearing when the user starts typing
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ─── Restore real React hooks (overrides global setupTests.js mock) ───────────
vi.mock('react', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual };
});

// ─── Override lucide-react (adds icons missing from global setupTests mock) ───
vi.mock('lucide-react', () => {
  const icon = (id) => () => <svg data-testid={id} />;
  return {
    Mail:        icon('mail-icon'),
    ShieldCheck: icon('shield-icon'),
    LogIn:       icon('login-icon'),
    Loader2:     icon('loader-icon'),
  };
});

// ─── Mock react-router-dom navigate ──────────────────────────────────────────
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useNavigate: () => mockNavigate };
});

// ─── Mock AuthContext ─────────────────────────────────────────────────────────
const mockLogin = vi.fn();
let mockIsAuthenticated = false;
vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ login: mockLogin, isAuthenticated: mockIsAuthenticated }),
}));

// ─── Mock API ─────────────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  verifyOtp: vi.fn(),
}));

import Login from './Login';
import { verifyOtp } from '../services/api';

// ─── Helpers ──────────────────────────────────────────────────────────────────
const renderLogin = () => render(<Login />);

const fillForm = (email = 'user@test.com', otp = '123456') => {
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: email } });
  fireEvent.change(screen.getByLabelText('6-Digit Code'), { target: { value: otp } });
};


// ══════════════════════════════════════════════════════════════════════════════
describe('Login — already authenticated redirect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
  });

  afterEach(() => {
    mockIsAuthenticated = false;
  });

  it('redirects to /dashboard when user is already authenticated', async () => {
    mockIsAuthenticated = true;
    renderLogin();
    await waitFor(() =>
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true })
    );
  });

  it('does not redirect when user is not authenticated', () => {
    mockIsAuthenticated = false;
    renderLogin();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Login — rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
  });

  it('renders the page heading "Secure Access"', () => {
    renderLogin();
    expect(screen.getByText('Secure Access')).toBeInTheDocument();
  });

  it('renders the email input', () => {
    renderLogin();
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
  });

  it('renders the OTP code input', () => {
    renderLogin();
    expect(screen.getByLabelText('6-Digit Code')).toBeInTheDocument();
  });

  it('renders the submit button "Verify and Enter"', () => {
    renderLogin();
    expect(screen.getByRole('button', { name: /verify and enter/i })).toBeInTheDocument();
  });

  it('renders the TOTP footer note', () => {
    renderLogin();
    expect(screen.getByText(/time-based one-time password/i)).toBeInTheDocument();
  });

  it('does not show an error message on initial render', () => {
    renderLogin();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Login — OTP input validation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
  });

  it('allows typing numeric digits', () => {
    renderLogin();
    const otpInput = screen.getByLabelText('6-Digit Code');
    fireEvent.change(otpInput, { target: { value: '123' } });
    expect(otpInput.value).toBe('123');
  });

  it('ignores non-numeric characters (letters)', () => {
    renderLogin();
    const otpInput = screen.getByLabelText('6-Digit Code');
    fireEvent.change(otpInput, { target: { value: 'abc' } });
    // handleOtpChange rejects non-digits — value stays empty
    expect(otpInput.value).toBe('');
  });

  it('ignores input beyond 6 digits', () => {
    renderLogin();
    const otpInput = screen.getByLabelText('6-Digit Code');
    fireEvent.change(otpInput, { target: { value: '1234567' } });
    expect(otpInput.value).toBe('');
  });

  it('accepts exactly 6 digits', () => {
    renderLogin();
    const otpInput = screen.getByLabelText('6-Digit Code');
    fireEvent.change(otpInput, { target: { value: '654321' } });
    expect(otpInput.value).toBe('654321');
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Login — form validation guards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
  });

  it('shows error when email is empty on submit', () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText('6-Digit Code'), { target: { value: '123456' } });
    fireEvent.submit(document.querySelector('form'));
    expect(screen.getByText('Please enter your email address')).toBeInTheDocument();
    expect(verifyOtp).not.toHaveBeenCalled();
  });

  it('shows error when OTP is empty on submit', () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } });
    fireEvent.submit(document.querySelector('form'));
    expect(screen.getByText('Please enter a valid 6-digit OTP code')).toBeInTheDocument();
    expect(verifyOtp).not.toHaveBeenCalled();
  });

  it('shows error when OTP has fewer than 6 digits', () => {
    renderLogin();
    fillForm('user@test.com', '123');
    fireEvent.submit(document.querySelector('form'));
    expect(screen.getByText('Please enter a valid 6-digit OTP code')).toBeInTheDocument();
    expect(verifyOtp).not.toHaveBeenCalled();
  });

  it('does not call verifyOtp when validation fails', () => {
    renderLogin();
    fireEvent.submit(document.querySelector('form'));
    expect(verifyOtp).not.toHaveBeenCalled();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Login — successful authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
    localStorage.clear();
    verifyOtp.mockResolvedValue({
      data: { status: 'success', access_token: 'jwt-token-abc', refresh_token: 'refresh-xyz' },
    });
  });

  it('calls verifyOtp with trimmed email and OTP', async () => {
    renderLogin();
    fillForm('  user@test.com  ', '123456');
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => expect(verifyOtp).toHaveBeenCalledWith({
      email: 'user@test.com',
      otp_code: '123456',
    }));
  });

  it('calls login() from AuthContext with access and refresh tokens on success', async () => {
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(mockLogin).toHaveBeenCalledWith('jwt-token-abc', 'refresh-xyz')
    );
  });

  it('navigates to /dashboard on success', async () => {
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/dashboard'));
  });

  it('shows the success message before navigating', async () => {
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(screen.getByText(/authentication successful/i)).toBeInTheDocument()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Login — failed authentication', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
    localStorage.clear();
  });

  it('shows error when API returns non-success status', async () => {
    verifyOtp.mockResolvedValue({ data: { status: 'error' } });
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(screen.getByText(/invalid email or otp code/i)).toBeInTheDocument()
    );
  });

  it('shows error when verifyOtp throws a network error', async () => {
    verifyOtp.mockRejectedValue(new Error('Network error'));
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(screen.getByText(/authentication failed/i)).toBeInTheDocument()
    );
  });

  it('does not store a token when authentication fails', async () => {
    verifyOtp.mockRejectedValue(new Error('Fail'));
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => screen.getByText(/authentication failed/i));
    expect(localStorage.getItem('access_token')).toBeNull();
  });

  it('does not navigate on authentication failure', async () => {
    verifyOtp.mockRejectedValue(new Error('Fail'));
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() => screen.getByText(/authentication failed/i));
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Login — loading state', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
  });

  it('disables the submit button while loading', async () => {
    verifyOtp.mockReturnValue(new Promise(() => {})); // never resolves
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /verifying/i })).toBeDisabled()
    );
  });

  it('shows "Verifying..." text while loading', async () => {
    verifyOtp.mockReturnValue(new Promise(() => {}));
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(screen.getByText('Verifying...')).toBeInTheDocument()
    );
  });

  it('re-enables the submit button after a failed request', async () => {
    verifyOtp.mockRejectedValue(new Error('Fail'));
    renderLogin();
    fillForm();
    fireEvent.submit(document.querySelector('form'));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /verify and enter/i })).not.toBeDisabled()
    );
  });
});

// ══════════════════════════════════════════════════════════════════════════════
describe('Login — error clearing on user input', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
  });

  it('clears the error when the user types in the email field', () => {
    renderLogin();
    fireEvent.submit(document.querySelector('form')); // triggers "Please enter your email"
    expect(screen.getByText('Please enter your email address')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a' } });
    expect(screen.queryByText('Please enter your email address')).not.toBeInTheDocument();
  });

  it('clears the error when the user types in the OTP field', () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'user@test.com' } });
    fireEvent.submit(document.querySelector('form')); // triggers OTP error
    expect(screen.getByText('Please enter a valid 6-digit OTP code')).toBeInTheDocument();

    // Type a digit — handleOtpChange clears error when error is set
    fireEvent.change(screen.getByLabelText('6-Digit Code'), { target: { value: '1' } });
    expect(screen.queryByText('Please enter a valid 6-digit OTP code')).not.toBeInTheDocument();
  });
});
