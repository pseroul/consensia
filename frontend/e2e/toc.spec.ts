/**
 * E2E tests for the Table of Contents page.
 *
 * Why these tests matter for the clustering refactor:
 *   The TOC page is the only UI surface that shows the ML pipeline's output.
 *   Any change to DataSimilarity, EmbeddingAnalyzer, TocTreeBuilder, or the
 *   TocEntry shape directly breaks these tests — which is the point.
 *
 * Contracts asserted:
 *
 * Rendering
 * - Page loads and calls GET /toc/structure on mount.
 * - A loading spinner is shown while the request is in flight.
 * - Heading entries (type="heading") are rendered with their title.
 * - Idea leaf entries (type="idea") are rendered with title and a content
 *   snippet under the heading they belong to.
 * - Originality scores (e.g. "45%") appear next to each entry.
 * - The section count in the page sub-heading reflects the number of top-level
 *   TOC items.
 * - When the API returns an empty array the empty-state message is shown.
 * - When the API returns an error the error message is shown.
 *
 * Tree interaction
 * - Clicking a heading toggles its children (collapse / re-expand).
 * - "Collapse All" button hides all children simultaneously.
 * - "Expand All" button after Collapse All restores all children.
 *
 * Content modal
 * - Clicking an idea leaf opens FullContentModal with the correct title.
 * - The modal displays the idea's full text content.
 * - Closing with the X button dismisses the modal.
 * - Closing with the "Close" button dismisses the modal.
 *
 * Refresh
 * - Clicking the "Refresh" button calls POST /toc/update then GET /toc/structure.
 * - The refreshed content replaces the old content in the UI.
 * - A spinner appears on the Refresh button while the update is in flight.
 * - An error during refresh shows the error message.
 *
 * Navigation
 * - "Back to Dashboard" link navigates to /dashboard.
 */

import { test, expect } from '@playwright/test';
import {
  setAuthToken,
  mockGetIdeas,
  mockGetUserIdeas,
  mockGetTocStructure,
  mockUpdateTocStructure,
  MOCK_TOC,
  API_URL,
} from './fixtures';


// ---------------------------------------------------------------------------
// Setup helper
// ---------------------------------------------------------------------------

async function goToToc({ page }: { page: import('@playwright/test').Page }) {
  await mockGetTocStructure(page);
  await page.goto('/');
  await setAuthToken(page);
  await page.goto('/table-of-contents');
  await page.waitForURL('/table-of-contents');
  // Wait for spinner to clear
  await expect(page.locator('.animate-spin').first()).not.toBeVisible({ timeout: 5_000 }).catch(() => {});
}


// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

test.describe('TOC rendering', () => {
  test.beforeEach(goToToc);

  test('shows heading titles from GET /toc/structure', async ({ page }) => {
    await expect(page.getByText('Machine Learning & AI')).toBeVisible();
  });

  test('shows idea leaf titles nested under their heading', async ({ page }) => {
    await expect(page.getByText('Neural Networks')).toBeVisible();
    await expect(page.getByText('Gradient Descent')).toBeVisible();
  });

  test('shows a top-level isolated idea leaf', async ({ page }) => {
    await expect(page.getByText('Isolated Idea')).toBeVisible();
  });

  test('shows originality scores', async ({ page }) => {
    await expect(page.getByText(/45%/)).toBeVisible();
    await expect(page.getByText(/95%/)).toBeVisible();
  });

  test('shows section count in the sub-heading', async ({ page }) => {
    // MOCK_TOC has 2 top-level items → "2 sections"
    await expect(page.getByText(/2 sections/)).toBeVisible();
  });

  test('shows a loading spinner while fetching', async ({ page }) => {
    await page.route(`${API_URL}/toc/structure`, async (route) => {
      await new Promise((r) => setTimeout(r, 400));
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TOC) });
    });
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/table-of-contents');

    await expect(page.locator('.animate-spin')).toBeVisible();
  });

  test('shows empty-state message when TOC is an empty array', async ({ page }) => {
    await page.route(`${API_URL}/toc/structure`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/table-of-contents');

    await expect(page.getByText(/no content available/i)).toBeVisible({ timeout: 5_000 });
  });

  test('shows error message when GET /toc/structure fails', async ({ page }) => {
    await page.route(`${API_URL}/toc/structure`, (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Internal error' }) })
    );
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/table-of-contents');

    await expect(page.getByText(/failed to load table of contents/i)).toBeVisible({ timeout: 5_000 });
  });
});


// ---------------------------------------------------------------------------
// Tree interaction (collapse / expand)
// ---------------------------------------------------------------------------

test.describe('TOC tree interaction', () => {
  test.beforeEach(goToToc);

  test('children are visible by default (expanded on load)', async ({ page }) => {
    await expect(page.getByText('Neural Networks')).toBeVisible();
    await expect(page.getByText('Gradient Descent')).toBeVisible();
  });

  test('clicking a heading collapses its children', async ({ page }) => {
    await page.getByRole('button', { name: /toggle machine learning/i }).click();
    await expect(page.getByText('Neural Networks')).not.toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Gradient Descent')).not.toBeVisible();
  });

  test('clicking a collapsed heading re-expands its children', async ({ page }) => {
    await page.getByRole('button', { name: /toggle machine learning/i }).click();
    await expect(page.getByText('Neural Networks')).not.toBeVisible();

    await page.getByRole('button', { name: /toggle machine learning/i }).click();
    await expect(page.getByText('Neural Networks')).toBeVisible();
  });

  test('"Collapse All" hides all nested children', async ({ page }) => {
    await page.getByRole('button', { name: /collapse all/i }).click();
    await expect(page.getByText('Neural Networks')).not.toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Gradient Descent')).not.toBeVisible();
  });

  test('"Expand All" after "Collapse All" restores all children', async ({ page }) => {
    await page.getByRole('button', { name: /collapse all/i }).click();
    await expect(page.getByText('Neural Networks')).not.toBeVisible();

    await page.getByRole('button', { name: /expand all/i }).click();
    await expect(page.getByText('Neural Networks')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Gradient Descent')).toBeVisible();
  });

  test('heading shows child count', async ({ page }) => {
    // MOCK_TOC heading has 2 children
    await expect(page.getByText(/\(2 items\)/)).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Content modal
// ---------------------------------------------------------------------------

test.describe('TOC content modal', () => {
  test.beforeEach(goToToc);

  test('clicking an idea leaf opens FullContentModal', async ({ page }) => {
    await page.getByRole('button', { name: /view details for neural networks/i }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('modal shows the correct idea title', async ({ page }) => {
    await page.getByRole('button', { name: /view details for neural networks/i }).click();
    await expect(page.getByRole('dialog').getByText('Neural Networks')).toBeVisible();
  });

  test('modal shows the full text content', async ({ page }) => {
    await page.getByRole('button', { name: /view details for neural networks/i }).click();
    await expect(
      page.getByRole('dialog').getByText('Deep learning fundamentals and backpropagation')
    ).toBeVisible();
  });

  test('closing modal with X button dismisses it', async ({ page }) => {
    await page.getByRole('button', { name: /view details for neural networks/i }).click();
    await page.getByRole('button', { name: /close modal/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 3_000 });
  });

  test('closing modal with "Close" button dismisses it', async ({ page }) => {
    await page.getByRole('button', { name: /view details for neural networks/i }).click();
    await page.getByRole('button', { name: /^close$/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 3_000 });
  });

  test('clicking an isolated idea leaf (root level) also opens the modal', async ({ page }) => {
    await page.getByRole('button', { name: /view details for isolated idea/i }).click();
    await expect(page.getByRole('dialog').getByText('Isolated Idea')).toBeVisible();
    await expect(
      page.getByRole('dialog').getByText('A standalone concept with high originality')
    ).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Refresh
// ---------------------------------------------------------------------------

test.describe('TOC refresh', () => {
  test.beforeEach(goToToc);

  test('clicking Refresh calls POST /toc/update then GET /toc/structure', async ({ page }) => {
    let postCalled = false;
    let getCalled = false;

    await page.route(`${API_URL}/toc/update`, (route) => {
      postCalled = true;
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'toc added successfully', llm_backend: 'ClaudeLlmClient' }) });
    });
    await page.route(`${API_URL}/toc/structure`, (route) => {
      getCalled = true;
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TOC) });
    });

    await page.getByRole('button', { name: /refresh content/i }).click();
    await page.waitForTimeout(500);

    expect(postCalled).toBe(true);
    expect(getCalled).toBe(true);
  });

  test('shows toast with LLM backend name after successful refresh', async ({ page }) => {
    await page.route(`${API_URL}/toc/update`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'toc added successfully', llm_backend: 'ClaudeLlmClient' }) })
    );
    await page.route(`${API_URL}/toc/structure`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TOC) })
    );

    await page.getByRole('button', { name: /refresh content/i }).click();

    await expect(page.getByRole('status')).toHaveText('TOC generated with ClaudeLlmClient', { timeout: 5_000 });
  });

  test('refreshed content replaces old content', async ({ page }) => {
    const updatedToc = [
      {
        title: 'New Section After Refresh',
        type: 'heading',
        originality: '60%',
        level: 1,
        children: [
          { title: 'Brand New Idea', type: 'idea', id: 'Brand New Idea', text: 'Fresh content', originality: '80%' },
        ],
      },
    ];

    await page.route(`${API_URL}/toc/update`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'toc added successfully', llm_backend: 'OllamaLlmClient' }) })
    );
    await page.route(`${API_URL}/toc/structure`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(updatedToc) })
    );

    await page.getByRole('button', { name: /refresh content/i }).click();

    await expect(page.getByText('New Section After Refresh')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('Machine Learning & AI')).not.toBeVisible();
  });

  test('Refresh button is disabled and shows spinner during update', async ({ page }) => {
    await page.route(`${API_URL}/toc/update`, async (route) => {
      await new Promise((r) => setTimeout(r, 400));
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'ok', llm_backend: 'TfidfFallbackClient' }) });
    });
    await page.route(`${API_URL}/toc/structure`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TOC) })
    );

    await page.getByRole('button', { name: /refresh content/i }).click();
    await expect(page.getByRole('button', { name: /refreshing/i })).toBeDisabled();
    await expect(page.locator('.animate-spin').first()).toBeVisible();
  });

  test('error during refresh shows error message', async ({ page }) => {
    await page.route(`${API_URL}/toc/update`, (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Clustering failed' }) })
    );

    await page.getByRole('button', { name: /refresh content/i }).click();
    await expect(page.getByText(/failed to refresh table of contents/i)).toBeVisible({ timeout: 5_000 });
  });
});


// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

test.describe('TOC navigation', () => {
  test('"Back to Dashboard" link navigates to /dashboard', async ({ page }) => {
    await mockGetTocStructure(page);
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/table-of-contents');
    await page.waitForURL('/table-of-contents');

    await page.getByRole('link', { name: /back to dashboard/i }).evaluate(el => (el as HTMLElement).click());
    await page.waitForURL('/dashboard');
    await expect(page).toHaveURL('/dashboard');
  });
});
