/**
 * api.test.js
 * Unit tests for the axios 401 response interceptor in api.js.
 *
 * Strategy: use vi.resetModules() + vi.doMock() in each beforeEach to load a
 * fresh copy of api.js with a custom axios mock that captures the interceptor
 * error handler.  We then call that handler directly to verify each code path.
 */

import { describe, it, expect, vi, beforeAll, afterAll, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// Helpers shared across test suites
// ---------------------------------------------------------------------------

/** Build a minimal axios-like error object. */
function makeError(status, url = '/ideas') {
  return {
    response: { status },
    config: { url, headers: {} },
  };
}

/** Spy on window.location.href writes (jsdom allows reassignment). */
function mockWindowLocation() {
  const original = window.location;
  delete window.location;
  window.location = { href: '' };
  return () => {
    window.location = original;
  };
}

// ---------------------------------------------------------------------------
// Shared setup: reload api.js with a fresh axios mock each test
// ---------------------------------------------------------------------------

let errorHandler;
let mockPost;
let mockRequest;
let restoreLocation;

async function setupApiModule() {
  mockPost = vi.fn();
  mockRequest = vi.fn();
  let capturedErrorHandler;

  vi.doMock('axios', () => ({
    default: {
      create: () => ({
        get: vi.fn(),
        post: mockPost,
        put: vi.fn(),
        delete: vi.fn(),
        request: mockRequest,
        interceptors: {
          request: { use: vi.fn() },
          response: {
            use: vi.fn((_ok, errFn) => {
              capturedErrorHandler = errFn;
            }),
          },
        },
      }),
    },
  }));

  await import('./api');
  errorHandler = capturedErrorHandler;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('api.js — 401 response interceptor — non-401 pass-through', () => {
  beforeEach(async () => {
    localStorage.clear();
    vi.resetModules();
    restoreLocation = mockWindowLocation();
    await setupApiModule();
  });

  afterEach(() => {
    vi.doUnmock('axios');
    restoreLocation();
    localStorage.clear();
  });

  it('rejects non-401 errors immediately without touching localStorage', async () => {
    localStorage.setItem('access_token', 'tok');
    const error = makeError(500);
    await expect(errorHandler(error)).rejects.toEqual(error);
    expect(localStorage.getItem('access_token')).toBe('tok');
  });

  it('rejects non-401 errors without redirecting', async () => {
    const error = makeError(403);
    await expect(errorHandler(error)).rejects.toEqual(error);
    expect(window.location.href).toBe('');
  });
});

describe('api.js — 401 response interceptor — anti-loop guard', () => {
  beforeEach(async () => {
    localStorage.clear();
    vi.resetModules();
    restoreLocation = mockWindowLocation();
    await setupApiModule();
  });

  afterEach(() => {
    vi.doUnmock('axios');
    restoreLocation();
    localStorage.clear();
  });

  it('clears localStorage and redirects if /auth/refresh itself returns 401', async () => {
    localStorage.setItem('access_token', 'tok');
    localStorage.setItem('refresh_token', 'rtok');
    const error = makeError(401, '/auth/refresh');
    await expect(errorHandler(error)).rejects.toEqual(error);
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(window.location.href).toBe('/');
  });
});

describe('api.js — 401 response interceptor — no refresh token', () => {
  beforeEach(async () => {
    localStorage.clear();
    vi.resetModules();
    restoreLocation = mockWindowLocation();
    await setupApiModule();
  });

  afterEach(() => {
    vi.doUnmock('axios');
    restoreLocation();
    localStorage.clear();
  });

  it('clears access_token and redirects when no refresh_token is stored', async () => {
    localStorage.setItem('access_token', 'tok');
    const error = makeError(401);
    await expect(errorHandler(error)).rejects.toEqual(error);
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(window.location.href).toBe('/');
  });
});

describe('api.js — 401 response interceptor — successful refresh', () => {
  beforeEach(async () => {
    localStorage.clear();
    vi.resetModules();
    restoreLocation = mockWindowLocation();
    await setupApiModule();
  });

  afterEach(() => {
    vi.doUnmock('axios');
    restoreLocation();
    localStorage.clear();
  });

  it('calls POST /auth/refresh with the stored refresh_token', async () => {
    localStorage.setItem('access_token', 'old-tok');
    localStorage.setItem('refresh_token', 'rtok');
    mockPost.mockResolvedValue({ data: { access_token: 'new-tok', refresh_token: 'new-rtok' } });
    mockRequest.mockResolvedValue({ data: [] });

    await errorHandler(makeError(401));

    expect(mockPost).toHaveBeenCalledWith('/auth/refresh', { refresh_token: 'rtok' });
  });

  it('stores the new access_token in localStorage after refresh', async () => {
    localStorage.setItem('access_token', 'old-tok');
    localStorage.setItem('refresh_token', 'rtok');
    mockPost.mockResolvedValue({ data: { access_token: 'new-tok', refresh_token: 'new-rtok' } });
    mockRequest.mockResolvedValue({ data: [] });

    await errorHandler(makeError(401));

    expect(localStorage.getItem('access_token')).toBe('new-tok');
  });

  it('stores the new refresh_token in localStorage after refresh', async () => {
    localStorage.setItem('access_token', 'old-tok');
    localStorage.setItem('refresh_token', 'rtok');
    mockPost.mockResolvedValue({ data: { access_token: 'new-tok', refresh_token: 'new-rtok' } });
    mockRequest.mockResolvedValue({ data: [] });

    await errorHandler(makeError(401));

    expect(localStorage.getItem('refresh_token')).toBe('new-rtok');
  });

  it('retries the original request with the new Authorization header', async () => {
    localStorage.setItem('access_token', 'old-tok');
    localStorage.setItem('refresh_token', 'rtok');
    mockPost.mockResolvedValue({ data: { access_token: 'new-tok', refresh_token: 'new-rtok' } });
    mockRequest.mockResolvedValue({ data: [] });

    await errorHandler(makeError(401));

    expect(mockRequest).toHaveBeenCalledWith(
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: 'Bearer new-tok' }) })
    );
  });
});

// ---------------------------------------------------------------------------
// Smoke tests: verify every exported API function is callable.
// Runs FIRST to load api.js under the global axios mock before the
// module-isolation tests reset the registry.
// ---------------------------------------------------------------------------

describe('api.js — exported function smoke tests', () => {
  let mod;

  beforeAll(async () => {
    vi.resetModules();
    vi.doMock('axios', () => ({
      default: {
        create: () => ({
          get: vi.fn().mockResolvedValue({}),
          post: vi.fn().mockResolvedValue({}),
          put: vi.fn().mockResolvedValue({}),
          delete: vi.fn().mockResolvedValue({}),
          request: vi.fn().mockResolvedValue({}),
          interceptors: {
            request: { use: vi.fn() },
            response: { use: vi.fn() },
          },
        }),
      },
    }));
    mod = await import('./api');
  });

  afterAll(() => {
    vi.doUnmock('axios');
  });

  it('all exported API functions are callable without throwing', () => {
    mod.getIdeas();
    mod.getIdeas(5);
    mod.getUserIdeas();
    mod.getIdeasFromTags('tag1');
    mod.getIdeasFromTags('tag1', 5);
    mod.getTocStructure();
    mod.updateTocStructure();
    mod.getTags();
    mod.getTags(5);
    mod.getSimilarIdeas('idea');
    mod.createIdea({ title: 'x', content: 'y' });
    mod.updateIdea(1, { title: 'x' });
    mod.deleteIdea(1, { title: 'x', content: 'y' });
    mod.deleteTag('tag');
    mod.verifyOtp({ email: 'a@b.com', otp_code: '123456' });
    mod.getBooks();
    mod.createBook({ title: 'b' });
    mod.deleteBook(1);
    mod.getBookAuthors(1);
    mod.addBookAuthor(1, 2);
    mod.removeBookAuthor(1, 2);
    mod.getUsers();
    mod.getIdeaVotes(1);
    mod.castVote(1, 1);
    mod.removeVote(1);
    mod.getImpactComments(1);
    mod.getBookImpactComments(1);
    mod.createImpactComment(1, 'content');
    mod.deleteImpactComment(1);
    mod.getAdminUsers();
    mod.createAdminUser({});
    mod.updateAdminUser(1, {});
    mod.deleteAdminUser(1);
  });
});

describe('api.js — 401 response interceptor — failed refresh', () => {
  beforeEach(async () => {
    localStorage.clear();
    vi.resetModules();
    restoreLocation = mockWindowLocation();
    await setupApiModule();
  });

  afterEach(() => {
    vi.doUnmock('axios');
    restoreLocation();
    localStorage.clear();
  });

  it('clears localStorage and redirects when refresh call fails', async () => {
    localStorage.setItem('access_token', 'old-tok');
    localStorage.setItem('refresh_token', 'rtok');
    mockPost.mockRejectedValue(new Error('refresh failed'));

    const error = makeError(401);
    await expect(errorHandler(error)).rejects.toThrow('refresh failed');
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
    expect(window.location.href).toBe('/');
  });
});
