/**
 * Shared helpers and sample data for E2E tests.
 *
 * Design principles:
 * - All API calls are intercepted with page.route() so tests run without a
 *   real backend.  The mock responses match the exact shape the frontend
 *   expects (IdeaItem, TagItem, etc.) so a schema change breaks the test.
 * - FAKE_TOKEN is a non-empty string – ProtectedRoute only checks
 *   localStorage.getItem('access_token') != null.  The real JWT format is
 *   not needed here because the backend is mocked.
 * - API_URL must match VITE_API_URL / the api.js default so route patterns
 *   intercept the right requests.
 */

import { Page, Route } from '@playwright/test';

export const API_URL = process.env.VITE_API_URL ?? 'http://localhost:8000';
// A minimal but structurally valid JWT: header.payload.signature
// payload decodes to {"sub":"test@example.com","is_admin":false}
// AuthContext only base64-decodes the payload — signature is never verified client-side.
export const FAKE_TOKEN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' +
  '.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiaXNfYWRtaW4iOmZhbHNlfQ' +
  '.ZmFrZQ';
export const FAKE_REFRESH_TOKEN = 'e2e-fake-refresh-token';

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

export async function setAuthToken(page: Page, token = FAKE_TOKEN): Promise<void> {
  await page.evaluate((t) => localStorage.setItem('access_token', t), token);
}

export async function clearAuthToken(page: Page): Promise<void> {
  await page.evaluate(() => localStorage.removeItem('access_token'));
}

export async function getStoredToken(page: Page): Promise<string | null> {
  return page.evaluate(() => localStorage.getItem('access_token'));
}

export async function setRefreshToken(page: Page, token = FAKE_REFRESH_TOKEN): Promise<void> {
  await page.evaluate((t) => localStorage.setItem('refresh_token', t), token);
}

export async function getStoredRefreshToken(page: Page): Promise<string | null> {
  return page.evaluate(() => localStorage.getItem('refresh_token'));
}

export async function setAuthTokens(
  page: Page,
  accessToken = FAKE_TOKEN,
  refreshToken = FAKE_REFRESH_TOKEN,
): Promise<void> {
  await page.evaluate(
    ([a, r]) => {
      localStorage.setItem('access_token', a);
      localStorage.setItem('refresh_token', r);
    },
    [accessToken, refreshToken],
  );
}

export function mockRefreshSuccess(
  page: Page,
  newAccessToken = FAKE_TOKEN,
  newRefreshToken = FAKE_REFRESH_TOKEN,
): Promise<void> {
  return page.route(`${API_URL}/auth/refresh`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: newAccessToken,
        refresh_token: newRefreshToken,
        token_type: 'bearer',
      }),
    })
  );
}

export function mockRefreshFail(page: Page): Promise<void> {
  return page.route(`${API_URL}/auth/refresh`, (route: Route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Could not validate refresh token' }),
    })
  );
}

// ---------------------------------------------------------------------------
// Sample data (mirrors the backend's IdeaItem shape)
// ---------------------------------------------------------------------------

export const MOCK_BOOKS = [
  { id: 1, title: 'Test Book' },
];

export const MOCK_IDEAS = [
  { id: 1, title: 'Machine Learning', content: 'Gradient descent basics', tags: 'ml;ai',  book_id: 1 },
  { id: 2, title: 'Python Tips',      content: 'Use list comprehensions', tags: 'python', book_id: 1 },
  { id: 3, title: 'React Hooks',      content: 'useState and useEffect patterns', tags: '', book_id: 1 },
];

export const MOCK_USER_IDEAS = [
  { id: 1, title: 'Machine Learning', content: 'Gradient descent basics', tags: 'ml;ai', book_id: 1 },
];

// ---------------------------------------------------------------------------
// Route mock helpers
// Each helper intercepts exactly one endpoint.  Compose them per-test so
// each test makes its own expectations about which routes are called.
// ---------------------------------------------------------------------------

export function mockGetBooks(page: Page, books = MOCK_BOOKS): Promise<void> {
  return page.route(`${API_URL}/books`, (route: Route) => {
    if (route.request().method() === 'GET') {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(books) });
    } else {
      route.continue();
    }
  });
}

export function mockGetIdeas(page: Page, ideas = MOCK_IDEAS): Promise<void> {
  return page.route(`${API_URL}/ideas`, (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ideas) })
  );
}

export function mockGetUserIdeas(page: Page, ideas = MOCK_USER_IDEAS): Promise<void> {
  return page.route(`${API_URL}/user/ideas`, (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ideas) })
  );
}

export function mockCreateIdea(page: Page, returnId = 42): Promise<void> {
  return page.route(`${API_URL}/ideas`, (route: Route) => {
    if (route.request().method() === 'POST') {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: returnId }) });
    } else {
      route.continue();
    }
  });
}

export function mockUpdateIdea(page: Page, id: number): Promise<void> {
  return page.route(`${API_URL}/ideas/${id}`, (route: Route) => {
    if (route.request().method() === 'PUT') {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'updated' }) });
    } else {
      route.continue();
    }
  });
}

export function mockDeleteIdea(page: Page, id: number): Promise<void> {
  return page.route(`${API_URL}/ideas/${id}`, (route: Route) => {
    if (route.request().method() === 'DELETE') {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'deleted' }) });
    } else {
      route.continue();
    }
  });
}

export function mockVerifyOtp(
  page: Page,
  success: boolean,
  token = FAKE_TOKEN,
  refreshToken = FAKE_REFRESH_TOKEN,
): Promise<void> {
  return page.route(`${API_URL}/verify-otp`, (route: Route) => {
    if (success) {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'success',
          message: 'Connection authorized',
          access_token: token,
          refresh_token: refreshToken,
          token_type: 'bearer',
        }),
      });
    } else {
      route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid or expired code' }),
      });
    }
  });
}

export function mockGetSimilarIdeas(page: Page, results = MOCK_IDEAS): Promise<void> {
  return page.route(`${API_URL}/ideas/similar/**`, (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(results) })
  );
}

/** Return 401 for every API call — triggers the axios interceptor logout path. */
export function mockAllRoutes401(page: Page): Promise<void> {
  return page.route(`${API_URL}/**`, (route: Route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Unauthorized' }),
    })
  );
}

// ---------------------------------------------------------------------------
// TOC sample data
//
// Shape mirrors the backend's TocEntry.to_dict() output:
//   { title, type, originality, id?, text?, level?, children? }
//
// MOCK_TOC has one heading with two idea leaves (typical clustering output)
// plus one isolated idea leaf at the root (HDBSCAN noise point).
// ---------------------------------------------------------------------------

export const MOCK_TOC = [
  {
    title: 'Machine Learning & AI',
    type: 'heading',
    originality: '45%',
    level: 1,
    children: [
      {
        title: 'Neural Networks',
        type: 'idea',
        id: 'Neural Networks',
        text: 'Deep learning fundamentals and backpropagation',
        originality: '72%',
      },
      {
        title: 'Gradient Descent',
        type: 'idea',
        id: 'Gradient Descent',
        text: 'Optimization algorithm for training models',
        originality: '38%',
      },
    ],
  },
  {
    title: 'Isolated Idea',
    type: 'idea',
    id: 'Isolated Idea',
    text: 'A standalone concept with high originality',
    originality: '95%',
  },
];

export function mockGetTocStructure(page: Page, toc = MOCK_TOC): Promise<void> {
  return page.route(`${API_URL}/toc/structure`, (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(toc) })
  );
}

export function mockUpdateTocStructure(page: Page): Promise<void> {
  return page.route(`${API_URL}/toc/update`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ message: 'toc added successfully', llm_backend: 'TfidfFallbackClient' }),
    })
  );
}

// ---------------------------------------------------------------------------
// Tags & Ideas sample data
//
// Three tags:
//   ml     → has 1 idea (Machine Learning, id 1)
//   python → has 1 idea (Python Tips, id 2)
//   orphan → has 0 ideas (shows the delete button in the UI)
//
// GET /ideas returns 3 ideas; idea 3 (React Hooks) belongs to no tag so it
// appears in the "Untagged Ideas" section at the bottom of the page.
// ---------------------------------------------------------------------------

export const MOCK_TAGS = [
  { name: 'ml' },
  { name: 'python' },
  { name: 'orphan' },
];

// Responses for GET /ideas/tags/{name}  (IdeaItem shape from the backend)
export const MOCK_IDEAS_BY_TAG: Record<string, object[]> = {
  ml:     [{ id: 1, title: 'Machine Learning', content: 'Gradient descent basics', tags: 'ml;ai' }],
  python: [{ id: 2, title: 'Python Tips',      content: 'Use list comprehensions', tags: 'python' }],
  orphan: [],
};

export function mockGetTags(page: Page, tags = MOCK_TAGS): Promise<void> {
  return page.route(`${API_URL}/tags`, (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(tags) })
  );
}

/**
 * Intercepts GET /ideas/tags/{name} for every tag defined in ideasByTag.
 * A separate route() call is registered per tag so patterns are exact.
 */
export async function mockGetIdeasFromTags(
  page: Page,
  ideasByTag = MOCK_IDEAS_BY_TAG,
): Promise<void> {
  for (const [tag, ideas] of Object.entries(ideasByTag)) {
    await page.route(`${API_URL}/ideas/tags/${tag}`, (route: Route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ideas) })
    );
  }
}

export function mockDeleteTag(page: Page, name: string): Promise<void> {
  return page.route(`${API_URL}/tags/${name}`, (route: Route) => {
    if (route.request().method() === 'DELETE') {
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: `Tag '${name}' removed successfully` }) });
    } else {
      route.continue();
    }
  });
}
