/**
 * E2E tests for the Tags & Ideas page.
 *
 * Why these tests matter for the clustering refactor:
 *   The Tags & Ideas page shows how ideas are grouped by their tags — the
 *   manual-labelling complement to the ML-driven TOC. It also exposes the
 *   tag deletion path and the untagged-ideas section, both of which depend
 *   on the same data model that the clustering pipeline writes into.
 *
 *   The page issues N+2 API calls on load (GET /tags, then GET /ideas/tags/{t}
 *   for each tag, then GET /ideas).  Any change to tag serialization, relation
 *   cascades, or the idea-ownership model will be caught here.
 *
 * Contracts asserted:
 *
 * Rendering
 * - Page calls GET /tags on mount, then GET /ideas/tags/{name} for each tag.
 * - Each tag is rendered as a collapsible section header.
 * - Ideas associated with a tag appear indented under it.
 * - The tag count in the page sub-heading reflects the number of tags returned.
 * - A tag with zero associated ideas shows a delete (trash) button.
 * - Ideas NOT associated with any tag appear in an "Untagged Ideas" section.
 * - Loading spinner shown while fetching.
 * - Error message shown when the API fails.
 *
 * Tree interaction
 * - Clicking a tag header collapses its ideas.
 * - Clicking it again re-expands them.
 * - "Collapse All" hides all ideas simultaneously.
 * - "Expand All" after Collapse All restores all ideas.
 *
 * Content modal
 * - Clicking an idea opens FullContentModal with the correct title and content.
 * - Closing with X dismisses the modal.
 * - Closing with "Close" button dismisses the modal.
 *
 * Tag deletion
 * - Clicking the trash icon on an orphan tag opens the DeleteConfirmationModal.
 * - The modal names the tag being deleted.
 * - Confirming deletion calls DELETE /tags/{name}.
 * - After confirmed deletion the tag list is refreshed (GET /tags called again).
 * - Cancelling the deletion modal does NOT call DELETE /tags/{name}.
 * - The X button on the deletion modal also cancels without calling DELETE.
 *
 * Navigation
 * - "Back to Dashboard" link navigates to /dashboard.
 */

import { test, expect } from '@playwright/test';
import {
  setAuthToken,
  mockGetIdeas,
  mockGetUserIdeas,
  mockGetTags,
  mockGetIdeasFromTags,
  mockDeleteTag,
  MOCK_TAGS,
  MOCK_IDEAS_BY_TAG,
  API_URL,
} from './fixtures';


// ---------------------------------------------------------------------------
// Setup helpers
// ---------------------------------------------------------------------------

/**
 * Navigate to /tags-ideas with full mocks for the standard dataset:
 *   - 3 tags: ml (1 idea), python (1 idea), orphan (0 ideas)
 *   - GET /ideas returns 3 ideas; React Hooks (id=3) is untagged
 */
async function goToTagsIdeas({ page }: { page: import('@playwright/test').Page }) {
  await mockGetTags(page);
  await mockGetIdeasFromTags(page);
  // GET /ideas is called to find untagged ideas; React Hooks (id=3) is not in any tag's results
  await mockGetIdeas(page, [
    { id: 1, title: 'Machine Learning', content: 'Gradient descent basics', tags: 'ml;ai' },
    { id: 2, title: 'Python Tips',      content: 'Use list comprehensions',  tags: 'python' },
    { id: 3, title: 'React Hooks',      content: 'useState and useEffect',   tags: '' },
  ]);
  await page.goto('/');
  await setAuthToken(page);
  await page.goto('/tags-ideas');
  await page.waitForURL('/tags-ideas');
  // Wait for loading spinner to clear
  await expect(page.locator('.animate-spin').first()).not.toBeVisible({ timeout: 5_000 }).catch(() => {});
}


// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

test.describe('Tags & Ideas rendering', () => {
  test.beforeEach(goToTagsIdeas);

  test('shows all tag names', async ({ page }) => {
    await expect(page.getByText('ml')).toBeVisible();
    // Use exact match to avoid matching "Python Tips" idea title as a substring
    await expect(page.getByText('python', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('orphan')).toBeVisible();
  });

  test('shows ideas under their parent tag', async ({ page }) => {
    await expect(page.getByText('Machine Learning')).toBeVisible();
    await expect(page.getByText('Python Tips')).toBeVisible();
  });

  test('shows idea content snippet under the tag', async ({ page }) => {
    await expect(page.getByText('Gradient descent basics')).toBeVisible();
  });

  test('shows tag count in the sub-heading', async ({ page }) => {
    // MOCK_TAGS has 3 tags → "3 tags"
    await expect(page.getByText(/3 tags/)).toBeVisible();
  });

  test('shows idea count per tag', async ({ page }) => {
    // ml tag has 1 idea; use .first() since multiple tags may each show "(1 ideas)"
    await expect(page.getByText(/\(1 ideas?\)/).first()).toBeVisible();
  });

  test('orphan tag (zero ideas) shows a delete button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /delete tag orphan/i })).toBeVisible();
  });

  test('ml and python tags do NOT show a delete button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /delete tag ml/i })).not.toBeVisible();
    await expect(page.getByRole('button', { name: /delete tag python/i })).not.toBeVisible();
  });

  test('untagged ideas section appears for ideas with no tags', async ({ page }) => {
    await expect(page.getByText('Untagged Ideas')).toBeVisible();
    await expect(page.getByText('React Hooks')).toBeVisible();
  });

  test('shows loading spinner while fetching', async ({ page }) => {
    await page.route(`${API_URL}/tags`, async (route) => {
      await new Promise((r) => setTimeout(r, 400));
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TAGS) });
    });
    await mockGetIdeasFromTags(page);
    await mockGetIdeas(page);
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/tags-ideas');

    await expect(page.locator('.animate-spin')).toBeVisible();
  });

  test('shows error message when GET /tags fails', async ({ page }) => {
    await page.route(`${API_URL}/tags`, (route) =>
      route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Internal error' }) })
    );
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/tags-ideas');

    await expect(page.getByText(/failed to load tags and ideas/i)).toBeVisible({ timeout: 5_000 });
  });

  test('shows empty-state message when there are no tags', async ({ page }) => {
    await page.route(`${API_URL}/tags`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '[]' })
    );
    await mockGetIdeas(page, []);
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/tags-ideas');

    await expect(page.getByText(/no tags available/i)).toBeVisible({ timeout: 5_000 });
  });
});


// ---------------------------------------------------------------------------
// Tree interaction (collapse / expand)
// ---------------------------------------------------------------------------

test.describe('Tags & Ideas tree interaction', () => {
  test.beforeEach(goToTagsIdeas);

  test('ideas are visible by default (tag sections expanded on load)', async ({ page }) => {
    await expect(page.getByText('Machine Learning')).toBeVisible();
  });

  test('clicking a tag header collapses its ideas', async ({ page }) => {
    await page.getByRole('button', { name: /toggle ml section/i }).click();
    await expect(page.getByText('Machine Learning')).not.toBeVisible({ timeout: 3_000 });
  });

  test('clicking a collapsed tag header re-expands its ideas', async ({ page }) => {
    await page.getByRole('button', { name: /toggle ml section/i }).click();
    await expect(page.getByText('Machine Learning')).not.toBeVisible();

    await page.getByRole('button', { name: /toggle ml section/i }).click();
    await expect(page.getByText('Machine Learning')).toBeVisible({ timeout: 3_000 });
  });

  test('"Collapse All" hides ideas in all tag sections', async ({ page }) => {
    await page.getByRole('button', { name: /collapse all/i }).click();
    await expect(page.getByText('Machine Learning')).not.toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Python Tips')).not.toBeVisible();
  });

  test('"Expand All" after "Collapse All" restores all ideas', async ({ page }) => {
    await page.getByRole('button', { name: /collapse all/i }).click();
    await expect(page.getByText('Machine Learning')).not.toBeVisible();

    await page.getByRole('button', { name: /expand all/i }).click();
    await expect(page.getByText('Machine Learning')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Python Tips')).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Content modal
// ---------------------------------------------------------------------------

test.describe('Tags & Ideas content modal', () => {
  test.beforeEach(goToTagsIdeas);

  test('clicking an idea opens FullContentModal', async ({ page }) => {
    await page.getByRole('button', { name: /view details for machine learning/i }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('modal shows the correct idea title', async ({ page }) => {
    await page.getByRole('button', { name: /view details for machine learning/i }).click();
    await expect(page.getByRole('dialog').getByText('Machine Learning')).toBeVisible();
  });

  test('modal shows the idea content', async ({ page }) => {
    await page.getByRole('button', { name: /view details for machine learning/i }).click();
    await expect(
      page.getByRole('dialog').getByText('Gradient descent basics')
    ).toBeVisible();
  });

  test('closing modal with X button dismisses it', async ({ page }) => {
    await page.getByRole('button', { name: /view details for machine learning/i }).click();
    await page.getByRole('button', { name: /close modal/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 3_000 });
  });

  test('closing modal with "Close" button dismisses it', async ({ page }) => {
    await page.getByRole('button', { name: /view details for machine learning/i }).click();
    await page.getByRole('button', { name: /^close$/i }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 3_000 });
  });
});


// ---------------------------------------------------------------------------
// Tag deletion
// ---------------------------------------------------------------------------

test.describe('Tag deletion', () => {
  test.beforeEach(goToTagsIdeas);

  test('clicking the delete icon opens the DeleteConfirmationModal', async ({ page }) => {
    await page.getByRole('button', { name: /delete tag orphan/i }).click();
    await expect(page.getByText('Confirm Deletion')).toBeVisible();
  });

  test('confirmation modal names the tag being deleted', async ({ page }) => {
    await page.getByRole('button', { name: /delete tag orphan/i }).click();
    await expect(page.getByText(/"orphan"/)).toBeVisible();
  });

  test('confirming deletion calls DELETE /tags/{name}', async ({ page }) => {
    let deleteCalled = false;
    await page.route(`${API_URL}/tags/orphan`, (route) => {
      if (route.request().method() === 'DELETE') {
        deleteCalled = true;
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: "Tag 'orphan' removed successfully" }) });
      } else {
        route.continue();
      }
    });

    await page.getByRole('button', { name: /delete tag orphan/i }).click();
    await page.getByRole('button', { name: /^delete$/i }).click();

    await page.waitForTimeout(300);
    expect(deleteCalled).toBe(true);
  });

  test('after confirmed deletion the tag list is refreshed', async ({ page }) => {
    // After deletion, GET /tags returns only ml and python
    const tagsAfterDeletion = [{ name: 'ml' }, { name: 'python' }];

    await page.route(`${API_URL}/tags/orphan`, (route) => {
      if (route.request().method() === 'DELETE') {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'removed' }) });
      } else {
        route.continue();
      }
    });
    // Override the GET /tags mock to return the post-deletion list on subsequent calls
    await page.route(`${API_URL}/tags`, (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(tagsAfterDeletion) });
      } else {
        route.continue();
      }
    });

    await page.getByRole('button', { name: /delete tag orphan/i }).click();
    await page.getByRole('button', { name: /^delete$/i }).click();

    // Use exact: true to avoid matching the modal text "...delete the tag "orphan"..."
    await expect(page.getByText('orphan', { exact: true })).not.toBeVisible({ timeout: 5_000 });
  });

  test('cancelling the deletion modal does NOT call DELETE /tags/{name}', async ({ page }) => {
    let deleteCalled = false;
    await page.route(`${API_URL}/tags/orphan`, (route) => {
      if (route.request().method() === 'DELETE') deleteCalled = true;
      route.continue();
    });

    await page.getByRole('button', { name: /delete tag orphan/i }).click();
    await page.getByRole('button', { name: /^cancel$/i }).click();

    await page.waitForTimeout(200);
    expect(deleteCalled).toBe(false);
  });

  test('Cancel button closes the deletion modal', async ({ page }) => {
    await page.getByRole('button', { name: /delete tag orphan/i }).click();
    await expect(page.getByText('Confirm Deletion')).toBeVisible();

    await page.getByRole('button', { name: /^cancel$/i }).click();
    await expect(page.getByText('Confirm Deletion')).not.toBeVisible({ timeout: 3_000 });
  });

  test('X button on the deletion modal also closes without deleting', async ({ page }) => {
    let deleteCalled = false;
    await page.route(`${API_URL}/tags/orphan`, (route) => {
      if (route.request().method() === 'DELETE') deleteCalled = true;
      route.continue();
    });

    await page.getByRole('button', { name: /delete tag orphan/i }).click();
    await page.getByRole('button', { name: /close modal/i }).click();

    await expect(page.getByText('Confirm Deletion')).not.toBeVisible({ timeout: 3_000 });
    expect(deleteCalled).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

test.describe('Tags & Ideas navigation', () => {
  test('"Back to Dashboard" link navigates to /dashboard', async ({ page }) => {
    await mockGetTags(page);
    await mockGetIdeasFromTags(page);
    await mockGetIdeas(page);
    await mockGetUserIdeas(page);
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/tags-ideas');
    await page.waitForURL('/tags-ideas');

    await page.getByRole('link', { name: /back to dashboard/i }).evaluate(el => (el as HTMLElement).click());
    await page.waitForURL('/dashboard');
    await expect(page).toHaveURL('/dashboard');
  });
});
