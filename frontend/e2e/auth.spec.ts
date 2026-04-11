/**
 * E2E tests for the authentication flow.
 *
 * Contracts asserted:
 * - Login page renders the email + OTP form.
 * - Client-side validation fires before any API call is made.
 * - A successful verify-otp response stores the token in localStorage and
 *   navigates to /dashboard.
 * - A 401 from verify-otp shows an error message and stays on the login page.
 * - Visiting a protected route without a token redirects to /.
 * - A 401 from any authenticated API call triggers the axios interceptor:
 *     token cleared from localStorage → window.location.href = '/' → back on login.
 * - Logout button removes the token and redirects to /.
 * - The Navbar is hidden on the login page (no token) and visible on the dashboard.
 */

import { test, expect } from '@playwright/test';
import {
  setAuthToken,
  setAuthTokens,
  clearAuthToken,
  getStoredToken,
  getStoredRefreshToken,
  mockVerifyOtp,
  mockGetIdeas,
  mockGetUserIdeas,
  mockAllRoutes401,
  mockRefreshFail,
  FAKE_TOKEN,
  FAKE_REFRESH_TOKEN,
  MOCK_IDEAS,
} from './fixtures';


// ---------------------------------------------------------------------------
// Login page rendering
// ---------------------------------------------------------------------------

test.describe('Login page', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure no stale token from a previous test
    await page.goto('/');
    await clearAuthToken(page);
    await page.reload();
  });

  test('renders email and OTP input fields', async ({ page }) => {
    await expect(page.locator('#email')).toBeVisible();
    await expect(page.locator('#otp')).toBeVisible();
  });

  test('renders the submit button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /verify and enter/i })).toBeVisible();
  });

  test('shows heading "Secure Access"', async ({ page }) => {
    await expect(page.getByText('Secure Access')).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Client-side form validation
// ---------------------------------------------------------------------------

test.describe('Login form validation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await clearAuthToken(page);
    await page.reload();
  });

  test('shows error when email is empty and form is submitted', async ({ page }) => {
    await page.locator('#otp').fill('123456');
    await page.getByRole('button', { name: /verify and enter/i }).click();
    await expect(page.getByText('Please enter your email address')).toBeVisible();
  });

  test('shows error when OTP has fewer than 6 digits', async ({ page }) => {
    await page.locator('#email').fill('user@example.com');
    await page.locator('#otp').fill('12345'); // only 5 digits
    await page.getByRole('button', { name: /verify and enter/i }).click();
    await expect(page.getByText('Please enter a valid 6-digit OTP code')).toBeVisible();
  });

  test('OTP input only accepts numeric characters', async ({ page }) => {
    await page.locator('#otp').fill('abc123');
    // The onChange handler strips non-digits, so only "123" remains
    const value = await page.locator('#otp').inputValue();
    expect(value).toMatch(/^\d*$/);
  });

  test('no API call is made when validation fails', async ({ page }) => {
    let apiCalled = false;
    await page.route('**/verify-otp', () => { apiCalled = true; });

    await page.getByRole('button', { name: /verify and enter/i }).click();
    // Short pause to confirm no request fires
    await page.waitForTimeout(200);
    expect(apiCalled).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// Login API flow
// ---------------------------------------------------------------------------

test.describe('Login API flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await clearAuthToken(page);
    await page.reload();
  });

  test('successful login stores token in localStorage and navigates to /dashboard', async ({ page }) => {
    await mockVerifyOtp(page, true);
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);

    await page.locator('#email').fill('user@example.com');
    await page.locator('#otp').fill('123456');
    await page.getByRole('button', { name: /verify and enter/i }).click();

    await page.waitForURL('/dashboard');

    const token = await getStoredToken(page);
    expect(token).toBe(FAKE_TOKEN);
  });

  test('failed login (401) shows error message and stays on login page', async ({ page }) => {
    await mockVerifyOtp(page, false);

    await page.locator('#email').fill('user@example.com');
    await page.locator('#otp').fill('000000');
    await page.getByRole('button', { name: /verify and enter/i }).click();

    await expect(page.getByText(/authentication failed/i)).toBeVisible();
    expect(page.url()).toContain('localhost:5173/');
    expect(page.url()).not.toContain('/dashboard');
  });

  test('loading spinner appears while request is in flight', async ({ page }) => {
    // Delay the mock so the loading state is observable
    await page.route('**/verify-otp', async (route) => {
      await new Promise((r) => setTimeout(r, 300));
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          access_token: FAKE_TOKEN,
          refresh_token: FAKE_REFRESH_TOKEN,
          token_type: 'bearer',
        }),
      });
    });
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);

    await page.locator('#email').fill('user@example.com');
    await page.locator('#otp').fill('123456');
    await page.getByRole('button', { name: /verify and enter/i }).click();

    await expect(page.getByText('Verifying...')).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Protected route guards
// ---------------------------------------------------------------------------

test.describe('Protected routes', () => {
  test('visiting /dashboard without a token redirects to /', async ({ page }) => {
    await page.goto('/');
    await clearAuthToken(page);

    await page.goto('/dashboard');
    await expect(page).toHaveURL('/');
  });

  test('visiting /table-of-contents without a token redirects to /', async ({ page }) => {
    await page.goto('/');
    await clearAuthToken(page);

    await page.goto('/table-of-contents');
    await expect(page).toHaveURL('/');
  });

  test('visiting /dashboard with a valid token stays on the page', async ({ page }) => {
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);

    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/dashboard');

    await expect(page).toHaveURL('/dashboard');
  });
});


// ---------------------------------------------------------------------------
// 401 interceptor (axios response interceptor contract)
// ---------------------------------------------------------------------------

test.describe('401 axios interceptor', () => {
  test('receiving 401 from the API clears localStorage token and redirects to /', async ({ page }) => {
    // Set a token so ProtectedRoute lets us in
    await page.goto('/');
    await setAuthToken(page);

    // Now make the dashboard API call return 401
    await mockAllRoutes401(page);
    await page.goto('/dashboard');

    // The axios interceptor does window.location.href = '/'
    await page.waitForURL('/');

    const token = await getStoredToken(page);
    expect(token).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// Logout
// ---------------------------------------------------------------------------

test.describe('Logout', () => {
  test.beforeEach(async ({ page }) => {
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);

    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/dashboard');
    await page.waitForURL('/dashboard');
  });

  test('clicking Disconnect clears localStorage token', async ({ page }) => {
    // Open the burger menu
    await page.getByRole('button', { name: '' }).first().click(); // burger button
    await page.getByRole('button', { name: /disconnect/i }).click();

    const token = await getStoredToken(page);
    expect(token).toBeNull();
  });

  test('clicking Disconnect redirects to the login page', async ({ page }) => {
    await page.getByRole('button', { name: '' }).first().click();
    await page.getByRole('button', { name: /disconnect/i }).click();

    await page.waitForURL('/');
    await expect(page.locator('#email')).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Refresh token flow
// ---------------------------------------------------------------------------

test.describe('Refresh token flow', () => {
  test('successful login stores both access_token and refresh_token', async ({ page }) => {
    await mockVerifyOtp(page, true);
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);

    await page.goto('/');
    await clearAuthToken(page);
    await page.evaluate(() => localStorage.removeItem('refresh_token'));

    await page.locator('#email').fill('user@example.com');
    await page.locator('#otp').fill('123456');
    await page.getByRole('button', { name: /verify and enter/i }).click();
    await page.waitForURL('/dashboard');

    expect(await getStoredToken(page)).toBe(FAKE_TOKEN);
    expect(await getStoredRefreshToken(page)).toBe(FAKE_REFRESH_TOKEN);
  });

  test('401 + refresh fails clears both tokens and redirects to /', async ({ page }) => {
    await page.goto('/');
    await setAuthTokens(page);

    // Register mockRefreshFail AFTER mockAllRoutes401 so it takes precedence for /auth/refresh
    await mockAllRoutes401(page);
    await mockRefreshFail(page);

    await page.goto('/dashboard');
    await page.waitForURL('/');

    expect(await getStoredToken(page)).toBeNull();
    expect(await getStoredRefreshToken(page)).toBeNull();
  });

  test('logout removes both access_token and refresh_token', async ({ page }) => {
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);

    await page.goto('/');
    await setAuthTokens(page);
    await page.goto('/dashboard');
    await page.waitForURL('/dashboard');

    // Trigger logout
    await page.getByRole('button', { name: '' }).first().click();
    await page.getByRole('button', { name: /disconnect/i }).click();
    await page.waitForURL('/');

    expect(await getStoredToken(page)).toBeNull();
    expect(await getStoredRefreshToken(page)).toBeNull();
  });
});


// ---------------------------------------------------------------------------
// Navbar visibility
// ---------------------------------------------------------------------------

test.describe('Navbar visibility', () => {
  test('navbar is not rendered on the login page (no token)', async ({ page }) => {
    await page.goto('/');
    await clearAuthToken(page);
    await page.reload();

    // Navbar checks localStorage.getItem('access_token') and returns null if absent
    await expect(page.locator('nav')).not.toBeVisible();
  });

  test('navbar is rendered on the dashboard (has token)', async ({ page }) => {
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);

    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/dashboard');

    await expect(page.locator('nav')).toBeVisible();
  });
});
