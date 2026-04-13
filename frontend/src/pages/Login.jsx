import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, ShieldCheck, LogIn, Loader2 } from 'lucide-react';
import { verifyOtp } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

/**
 * Login Component - Handles user authentication with OTP verification
 * 
 * This component provides:
 * - Email input field
 * - 6-digit OTP code input
 * - Secure authentication flow
 * - Error handling and user feedback
 * - Responsive design
 * 
 * Features:
 * - Form validation
 * - Loading states
 * - Error messaging
 * - Accessible UI components
 */
const Login = () => {
  // Navigation hook for routing
  const navigate = useNavigate();
  const { login, isAuthenticated } = useAuth();

  // Redirect to dashboard if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  // State management for form data
  const [email, setEmail] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  /**
   * Handle form submission for login
   * @async
   * @param {Object} e - Event object from form submission
   * @returns {Promise<void>}
   */
  const handleLogin = async (e) => {
    e.preventDefault();
    
    // Validate inputs
    if (!email.trim()) {
      setError('Please enter your email address');
      return;
    }
    
    if (!otpCode.trim() || otpCode.length !== 6 || !/^\d{6}$/.test(otpCode)) {
      setError('Please enter a valid 6-digit OTP code');
      return;
    }

    try {
      setIsLoading(true);
      setError(''); // Clear previous errors
      setSuccess(false);
      
      // Call API to verify OTP
      const response = await verifyOtp({ 
        email: email.trim(), 
        otp_code: otpCode.trim() 
      });
      
      // Check if authentication was successful
      if (response && response.data && response.data.status === 'success') {
        // Store access + refresh tokens and decode user info via AuthContext
        login(response.data.access_token, response.data.refresh_token);
        setSuccess(true);
        // Navigate to dashboard
        navigate('/dashboard');
      } else {
        setError('Invalid email or OTP code. Please try again.');
      }
    } catch (err) {
      console.error('Login error:', err);
      setError('Authentication failed. Please check your connection and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Handle OTP code input changes with validation
   * @param {Object} e - Event object from input change
   * @returns {void}
   */
  const handleOtpChange = (e) => {
    const value = e.target.value;
    // Allow only numeric characters and limit to 6 digits
    if (/^\d{0,6}$/.test(value)) {
      setOtpCode(value);
      // Clear error when user starts typing
      if (error) setError('');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
        
        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-50 rounded-full mb-4">
            <ShieldCheck className="text-blue-600" size={32} />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Secure Access</h2>
          <p className="text-gray-500 mt-2 text-sm">Enter your Google Authenticator code</p>
        </div>

        {/* Error message display */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {/* Success message display */}
        {success && (
          <div className="mb-6 p-4 bg-green-50 text-green-700 rounded-lg">
            Authentication successful! Redirecting...
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-6">
          {/* Email input field */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 ml-1" htmlFor="email">
              Email
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-3 text-gray-400" size={20} aria-hidden="true" />
              <input 
                id="email"
                type="email" 
                placeholder="your@email.com" 
                className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all bg-gray-50"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  // Clear error when user starts typing
                  if (error) setError('');
                }}
                required
                aria-invalid={!!error && email.trim() === ''}
                aria-describedby={error && email.trim() === '' ? "email-error" : undefined}
              />
            </div>
          </div>

          {/* OTP code input field */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 ml-1" htmlFor="otp">
              6-Digit Code
            </label>
            <div className="relative">
              <ShieldCheck className="absolute left-3 top-3 text-gray-400" size={20} aria-hidden="true" />
              <input 
                id="otp"
                type="text" 
                inputMode="numeric"
                maxLength="6"
                placeholder="000 000" 
                className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-600 focus:outline-none transition-all bg-gray-50 text-center text-2xl tracking-[0.5em] font-mono"
                value={otpCode}
                onChange={handleOtpChange}
                required
                aria-invalid={!!error && otpCode.length !== 6}
                aria-describedby={error && otpCode.length !== 6 ? "otp-error" : undefined}
              />
            </div>
            <p className="text-xs text-gray-500 text-center">
              Enter the 6-digit code from your authenticator app
            </p>
          </div>

          <button 
            type="submit" 
            disabled={isLoading}
            className="w-full bg-gray-900 hover:bg-black text-white font-bold py-4 rounded-xl flex items-center justify-center gap-2 transition-all transform hover:scale-[1.02] active:scale-95 shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            aria-busy={isLoading}
          >
            {isLoading ? (
              <>
                <Loader2 className="animate-spin" size={20} />
                Verifying...
              </>
            ) : (
              <>
                <LogIn size={20} />
                Verify and Enter
              </>
            )}
          </button>
        </form>

        <p className="text-center text-xs text-gray-400 mt-8">
          Time-based One-Time Password (TOTP) authentication system
        </p>
      </div>
    </div>
  );
};

export default Login;