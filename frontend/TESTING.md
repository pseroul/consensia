# Testing Guide for Brainiac5 Frontend

## Overview

The frontend has two test layers with different purposes:

| Layer | Location | Framework | What it tests |
|---|---|---|---|
| Unit | `src/**/*.test.jsx` | Vitest + React Testing Library | Component rendering and behaviour in JSDOM |
| E2E | `e2e/` | Playwright | Real browser: full page flows with mocked API |

Both layers are independent and can run simultaneously.

---

## Running Tests

```bash
cd frontend

# Unit tests
npm test                    # run once
npm run test:watch          # watch mode
npm run test:coverage       # with coverage (80% threshold)

# E2E tests (requires installation -- see below)
npm run test:e2e            # headless Chromium
npm run test:e2e:ui         # Playwright interactive UI
```

---

## Test Structure

```
frontend/
+-- playwright.config.ts          # Playwright configuration
+-- e2e/
|   +-- fixtures.ts               # shared helpers: setAuthToken, mock route helpers, sample data
|   +-- auth.spec.ts              # login form, validation, protected routes, logout, 401 interceptor
|   +-- ideas-crud.spec.ts        # dashboard rendering, create/edit/delete, search, similar ideas
|   +-- toc.spec.ts               # TOC page: rendering, tree interaction, modal, refresh, navigation
|   +-- tags-ideas.spec.ts        # Tags & Ideas page: tag/idea rendering, modal, tag deletion
+-- src/
    +-- components/
    |   +-- Navbar.test.jsx
    |   +-- IdeaModal.test.jsx     # also tests that Impact section renders in edit mode
    |   +-- ImpactComments.test.jsx# list, add, delete, 403 error message
    |   +-- VoteButtons.test.jsx
    |   +-- BookSelector.test.jsx
    +-- contexts/
    |   +-- AuthContext.test.jsx
    |   +-- BookContext.test.jsx
    +-- pages/
    |   +-- Login.test.jsx
    |   +-- TableOfContents.test.jsx # includes impact comments in markdown export
    |   +-- TagsIdeasPage.test.jsx
    |   +-- BooksPage.test.jsx
    |   +-- AdminPage.test.jsx
    +-- setupTests.js              # global mocks (React Router, axios, localStorage, icons)
```

---

## Unit Tests (Vitest)

Unit tests use Vitest with JSDOM and React Testing Library. API calls are mocked
with MSW. Global mocks in `setupTests.js` cover React Router, axios, and Lucide
icons so each test file can focus on a single component.

```bash
npm run test:coverage   # enforces 80% threshold (lines, functions, branches, statements)
```

### Writing a unit test

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import MyComponent from './MyComponent';

describe('MyComponent', () => {
  it('shows an error when input is empty', async () => {
    render(<MyComponent />);
    fireEvent.click(screen.getByRole('button', { name: /submit/i }));
    await waitFor(() => {
      expect(screen.getByText('Field is required')).toBeInTheDocument();
    });
  });
});
```

---

## E2E Tests (Playwright)

E2E tests run a real Chromium browser against the Vite dev server. Every API call
is intercepted with `page.route()` so no real backend is needed.

### Installation (once)

```bash
cd frontend
npm install
npx playwright install chromium
```

### Running

```bash
# Playwright can start the dev server automatically (reuseExistingServer: true):
npm run test:e2e

# Or start the dev server yourself first, then run tests:
npm run dev          # terminal 1
npm run test:e2e     # terminal 2
```

### Configuration

`playwright.config.ts` sets:
- `baseURL`: `http://localhost:5173`
- `workers: 1` -- sequential execution (Raspberry Pi resource constraint)
- `webServer.reuseExistingServer: true` -- reuses a running dev server
- Chromium only

### fixtures.ts

Shared helpers used across all spec files:

```typescript
import {
  setAuthToken,          // localStorage.setItem('access_token', token)
  clearAuthToken,        // localStorage.removeItem('access_token')
  getStoredToken,        // returns current token or null
  FAKE_TOKEN,            // non-empty string -- ProtectedRoute only checks != null
  MOCK_IDEAS,            // sample IdeaItem array matching the backend shape
  mockGetIdeas,          // intercepts GET /ideas -> 200 + MOCK_IDEAS
  mockGetUserIdeas,      // intercepts GET /user/ideas
  mockCreateIdea,        // intercepts POST /ideas
  mockUpdateIdea,        // intercepts PUT /ideas/{id}
  mockDeleteIdea,        // intercepts DELETE /ideas/{id}
  mockVerifyOtp,         // intercepts POST /verify-otp (pass success: true/false)
  mockGetSimilarIdeas,   // intercepts GET /ideas/similar/**
  mockAllRoutes401,      // intercepts everything -> 401 (triggers the axios interceptor)
  // TOC
  MOCK_TOC,              // sample TocEntry tree (1 heading + 2 leaves + 1 isolated leaf)
  mockGetTocStructure,   // intercepts GET /toc/structure
  mockUpdateTocStructure,// intercepts POST /toc/update
  // Tags & Ideas
  MOCK_TAGS,             // [{name:'ml'},{name:'python'},{name:'orphan'}]
  MOCK_IDEAS_BY_TAG,     // {ml:[...], python:[...], orphan:[]}
  mockGetTags,           // intercepts GET /tags
  mockGetIdeasFromTags,  // intercepts GET /ideas/tags/{name} for each tag in the map
  mockDeleteTag,         // intercepts DELETE /tags/{name}
} from './fixtures';
```

### API URL

Route patterns match `http://localhost:8000/**` (the default `VITE_API_URL`).
Override via environment variable if your backend runs on a different port:

```bash
VITE_API_URL=http://localhost:9000 npm run test:e2e
```

### Writing an E2E test

```typescript
import { test, expect } from '@playwright/test';
import { setAuthToken, mockGetIdeas, mockGetUserIdeas } from './fixtures';

test('dashboard shows ideas from the API', async ({ page }) => {
  // Set up route mocks BEFORE navigating -- requests fire immediately on load
  await mockGetIdeas(page);
  await mockGetUserIdeas(page);

  // Inject the auth token directly (no real OTP needed)
  await page.goto('/');
  await setAuthToken(page);
  await page.goto('/dashboard');

  await expect(page.getByText('Machine Learning')).toBeVisible();
});
```

### Key contracts tested by E2E

**auth.spec.ts** (18 tests):

| Contract | Test name |
|---|---|
| Empty email -> validation error, no API call | `shows error when email is empty` |
| OTP fewer than 6 digits -> validation error | `shows error when OTP has fewer than 6 digits` |
| OTP input strips non-numeric characters | `OTP input only accepts numeric characters` |
| Successful login stores JWT in localStorage | `successful login stores token in localStorage` |
| Successful login navigates to /dashboard | `successful login ... and navigates to /dashboard` |
| 401 from verify-otp shows error, stays on page | `failed login (401) shows error message` |
| /dashboard without token -> redirect to / | `visiting /dashboard without a token redirects to /` |
| 401 from API -> axios interceptor clears token + redirects | `receiving 401 from the API clears localStorage token` |
| Logout clears token + navigates to / | `clicking Disconnect clears localStorage token` |
| Navbar hidden when no token | `navbar is not rendered on the login page` |

**toc.spec.ts** (21 tests):

| Contract | Test name |
|---|---|
| Headings and idea leaves rendered from GET /toc/structure | `shows heading titles from GET /toc/structure` |
| Originality scores shown on entries | `shows originality scores` |
| Section count shown in sub-heading | `shows section count in the sub-heading` |
| Empty array -> empty-state message | `shows empty-state message when TOC is an empty array` |
| 500 response -> error message | `shows error message when GET /toc/structure fails` |
| Clicking heading collapses / re-expands children | `clicking a heading collapses its children` |
| "Collapse All" hides all children | `"Collapse All" hides all nested children` |
| "Expand All" restores all children | `"Expand All" after "Collapse All" restores all children` |
| Clicking idea leaf opens FullContentModal | `clicking an idea leaf opens FullContentModal` |
| Modal shows correct title and full text | `modal shows the full text content` |
| X closes modal; "Close" button closes modal | two separate tests |
| Refresh calls POST /toc/update then GET /toc/structure | `clicking Refresh calls POST /toc/update then GET /toc/structure` |
| Refresh replaces old content with new | `refreshed content replaces old content` |
| Refresh button disabled + spinner during update | `Refresh button is disabled and shows spinner during update` |
| Error during refresh -> error message | `error during refresh shows error message` |
| "Back to Dashboard" navigates to /dashboard | navigation test |

**tags-ideas.spec.ts** (22 tests):

| Contract | Test name |
|---|---|
| All tags rendered; ideas shown under parent tag | `shows all tag names` / `shows ideas under their parent tag` |
| Tag count shown in sub-heading | `shows tag count in the sub-heading` |
| Idea count shown per tag | `shows idea count per tag` |
| Tag with zero ideas shows delete button | `orphan tag (zero ideas) shows a delete button` |
| Tags with ideas do NOT show delete button | `ml and python tags do NOT show a delete button` |
| Untagged ideas appear in "Untagged Ideas" section | `untagged ideas section appears for ideas with no tags` |
| 500 response -> error message | `shows error message when GET /tags fails` |
| Empty tags -> empty-state message | `shows empty-state message when there are no tags` |
| Clicking tag collapses / re-expands ideas | `clicking a tag header collapses its ideas` |
| "Collapse All" / "Expand All" | two tests |
| Clicking idea opens FullContentModal with title and content | `clicking an idea opens FullContentModal` |
| X and "Close" dismiss modal | two tests |
| Delete icon opens DeleteConfirmationModal naming the tag | `clicking the delete icon opens the DeleteConfirmationModal` |
| Confirming calls DELETE /tags/{name} | `confirming deletion calls DELETE /tags/{name}` |
| After deletion the tag list is refreshed | `after confirmed deletion the tag list is refreshed` |
| Cancelling does NOT call DELETE | `cancelling the deletion modal does NOT call DELETE /tags/{name}` |
| X on deletion modal also closes without deleting | `X button on the deletion modal also closes without deleting` |
| "Back to Dashboard" navigates to /dashboard | navigation test |

**ideas-crud.spec.ts** (26 tests):

| Contract | Test name |
|---|---|
| Tags split on `;` -> rendered as individual chips | `renders tags as individual chips split on ";"` |
| Enter key in tag input creates a chip | `pressing Enter in tag input adds a tag chip` |
| Tags joined with `;` in POST /ideas body | `saving a new idea calls POST /ideas with semicolon-joined tags` |
| Cancel closes modal, no POST call | `Cancel button closes modal without calling POST /ideas` |
| Edit prefills modal with semicolon-split tags | `edit modal splits semicolon-separated tags into chips` |
| Saving edit calls PUT /ideas/{id} | `saving an edited idea calls PUT /ideas/{id}` |
| Accepting window.confirm calls DELETE | `accepting the confirm dialog calls DELETE /ideas/{id}` |
| Dismissing window.confirm does not call DELETE | `cancelling the confirm dialog does NOT call DELETE` |
| Search box filters client-side, no extra GET | `typing in the search box filters cards without calling GET /ideas again` |
| My Ideas radio calls GET /user/ideas | `"My Ideas" radio triggers GET /user/ideas` |
| Similar button calls GET /ideas/similar/{term} | `clicking "Similar" calls GET /ideas/similar/{term}` |

### window.confirm (delete dialog)

The delete flow uses `window.confirm`. Handle it in Playwright with:

```typescript
page.once('dialog', (dialog) => dialog.accept());   // confirm delete
page.once('dialog', (dialog) => dialog.dismiss());  // cancel delete
await page.getByRole('button', { name: /delete idea/i }).click();
```

If the dialog is replaced with a custom modal during a refactor, these two tests
will fail -- which is the correct signal that the contract has changed.

---

## Coverage

Unit tests enforce **>= 80%** coverage (configured in `vitest.config.ts`):

```bash
npm run test:coverage   # fails if any threshold is below 80%
```

E2E tests do not contribute to Vitest coverage reporting -- they are
complementary to, not a replacement for, the unit test layer.

---

## Quality Gate

```bash
npm run validate    # ESLint + knip (dead code detection)
npm run test:ci     # Vitest with coverage
npm run test:e2e    # Playwright E2E
```

Dead code flagged by knip must be deleted, not suppressed.
