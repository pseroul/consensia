/**
 * E2E tests for Dashboard idea CRUD operations.
 *
 * Contracts asserted:
 * - Dashboard fetches and renders ideas from GET /ideas on load.
 * - A loading spinner is shown while the request is in flight.
 * - Tags are split on ';' and rendered as individual chips.
 * - "New" button opens the IdeaModal.
 * - Tags are entered by typing in the tag input and pressing Enter; each tag
 *   becomes a chip.  The chip's × button removes the tag.
 * - The modal assembles tags back into a semicolon-joined string before
 *   calling POST /ideas (the serialization contract).
 * - Cancel closes the modal without making any API call.
 * - The edit (pencil) button opens the modal prefilled with the idea's data,
 *   including tags split from the semicolon-separated string.
 * - Saving an edit calls PUT /ideas/{id}.
 * - The delete (trash) button triggers window.confirm.
 *   Accepting calls DELETE /ideas/{id} and removes the card from the UI.
 *   Cancelling does not call DELETE.
 * - The search box filters ideas client-side by title/content/tags without
 *   firing additional API requests.
 * - "My Ideas" radio calls GET /user/ideas; "All Ideas" radio calls GET /ideas.
 * - The "Similar" button calls GET /ideas/similar/{term} and replaces the list.
 */

import { test, expect } from '@playwright/test';
import {
  setAuthToken,
  mockGetIdeas,
  mockGetUserIdeas,
  mockGetBooks,
  mockCreateIdea,
  mockUpdateIdea,
  mockDeleteIdea,
  mockGetSimilarIdeas,
  MOCK_IDEAS,
  MOCK_USER_IDEAS,
  API_URL,
} from './fixtures';


// ---------------------------------------------------------------------------
// Setup helper: navigate to /dashboard as an authenticated user
// ---------------------------------------------------------------------------

// Accepts the Playwright fixtures object so it can be passed directly to
// test.beforeEach() as well as called explicitly inside a test body.
async function goToDashboard({ page }: { page: import('@playwright/test').Page }) {
  await mockGetBooks(page);
  await mockGetIdeas(page);
  await mockGetUserIdeas(page);
  await page.goto('/');
  await setAuthToken(page);
  await page.goto('/dashboard');
  await page.waitForURL('/dashboard');
  // Wait for the loading spinner to disappear
  await expect(page.getByRole('status').or(page.locator('.animate-spin').first())).not.toBeVisible({ timeout: 5_000 }).catch(() => {});
  // Select the test book so the "New" button is enabled and book-based filtering works
  await page.selectOption('[data-testid="book-selector"]', { value: '1' });
  await expect(page.getByRole('button', { name: /new/i })).toBeEnabled();
}


// ---------------------------------------------------------------------------
// Dashboard rendering
// ---------------------------------------------------------------------------

test.describe('Dashboard rendering', () => {
  test('shows all ideas returned by GET /ideas', async ({ page }) => {
    await goToDashboard({ page });

    for (const idea of MOCK_IDEAS) {
      await expect(page.getByText(idea.title)).toBeVisible();
    }
  });

  test('renders tags as individual chips split on ";"', async ({ page }) => {
    await goToDashboard({ page });

    // "Machine Learning" has tags "ml;ai" → two chips
    await expect(page.getByText('ml')).toBeVisible();
    await expect(page.getByText('ai')).toBeVisible();
  });

  test('shows a loading spinner while fetching', async ({ page }) => {
    // Delay the mock so the spinner is observable
    await page.route(`${API_URL}/ideas`, async (route) => {
      await new Promise((r) => setTimeout(r, 400));
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IDEAS) });
    });
    await mockGetUserIdeas(page);
    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/dashboard');

    await expect(page.locator('.animate-spin')).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Create idea
// ---------------------------------------------------------------------------

test.describe('Create idea', () => {
  test.beforeEach(goToDashboard);

  test('"New" button opens the IdeaModal', async ({ page }) => {
    await page.getByRole('button', { name: /new/i }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('modal has title, content and tag input fields', async ({ page }) => {
    await page.getByRole('button', { name: /new/i }).click();
    await expect(page.locator('#title')).toBeVisible();
    await expect(page.locator('#content')).toBeVisible();
    await expect(page.getByPlaceholder(/ajouter un tag/i)).toBeVisible();
  });

  test('pressing Enter in tag input adds a tag chip', async ({ page }) => {
    await page.getByRole('button', { name: /new/i }).click();
    await page.getByPlaceholder(/ajouter un tag/i).fill('react');
    await page.getByPlaceholder(/ajouter un tag/i).press('Enter');

    await expect(page.getByText('#react')).toBeVisible();
  });

  test('clicking × on a tag chip removes it', async ({ page }) => {
    await page.getByRole('button', { name: /new/i }).click();
    const tagInput = page.getByPlaceholder(/ajouter un tag/i);
    await tagInput.fill('removeme');
    await tagInput.press('Enter');
    await expect(page.getByText('#removeme')).toBeVisible();

    // The × button inside the chip (evaluate: Playwright can't click outside-viewport modal buttons)
    await page.getByText('#removeme').locator('..').getByRole('button').evaluate((el: HTMLElement) => el.click());
    await expect(page.getByText('#removeme')).not.toBeVisible();
  });

  test('saving a new idea calls POST /ideas with semicolon-joined tags', async ({ page }) => {
    // Re-mock to intercept and capture the POST body BEFORE the GET that fires after save
    let capturedBody: Record<string, unknown> | null = null;
    await page.route(`${API_URL}/ideas`, async (route) => {
      if (route.request().method() === 'POST') {
        capturedBody = route.request().postDataJSON() as Record<string, unknown>;
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ id: 99 }) });
      } else {
        // GET /ideas called after refresh – return updated list
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IDEAS) });
      }
    });

    await page.getByRole('button', { name: /new/i }).click();
    await page.locator('#title').fill('My New Idea');
    await page.locator('#content').fill('Some content here');

    const tagInput = page.getByPlaceholder(/ajouter un tag/i);
    await tagInput.fill('alpha');
    await tagInput.press('Enter');
    await tagInput.fill('beta');
    await tagInput.press('Enter');

    await page.getByTestId('submit-button').evaluate((el: HTMLElement) => el.click());

    // Wait for modal to close (save succeeded)
    await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 5_000 });

    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.title).toBe('My New Idea');
    expect(capturedBody!.content).toBe('Some content here');
    // Tags serialised as semicolon-joined string – order may vary
    const tags = (capturedBody!.tags as string).split(';').sort();
    expect(tags).toEqual(['alpha', 'beta']);
  });

  test('Cancel button closes modal without calling POST /ideas', async ({ page }) => {
    let postCalled = false;
    await page.route(`${API_URL}/ideas`, (route) => {
      if (route.request().method() === 'POST') postCalled = true;
      route.continue();
    });

    await page.getByRole('button', { name: /new/i }).click();
    await page.locator('#title').fill('Abandoned idea');
    await page.getByRole('button', { name: /cancel/i }).evaluate((el: HTMLElement) => el.click());

    await expect(page.getByRole('dialog')).not.toBeVisible();
    expect(postCalled).toBe(false);
  });
});


// ---------------------------------------------------------------------------
// Edit idea
// ---------------------------------------------------------------------------

test.describe('Edit idea', () => {
  test.beforeEach(goToDashboard);

  test('edit button opens modal prefilled with the idea title', async ({ page }) => {
    // Click the edit button on the first idea card ("Machine Learning")
    await page.getByRole('button', { name: /edit idea/i }).first().click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.locator('#title')).toHaveValue('Machine Learning');
  });

  test('edit modal prefills content field', async ({ page }) => {
    await page.getByRole('button', { name: /edit idea/i }).first().click();
    await expect(page.locator('#content')).toHaveValue('Gradient descent basics');
  });

  test('edit modal splits semicolon-separated tags into chips', async ({ page }) => {
    // Idea 1 has tags "ml;ai"
    await page.getByRole('button', { name: /edit idea/i }).first().click();
    await expect(page.getByText('#ml')).toBeVisible();
    await expect(page.getByText('#ai')).toBeVisible();
  });

  test('saving an edited idea calls PUT /ideas/{id}', async ({ page }) => {
    await mockUpdateIdea(page, 1);

    let putCalled = false;
    await page.route(`${API_URL}/ideas/1`, (route) => {
      if (route.request().method() === 'PUT') putCalled = true;
      route.continue();
    });

    await page.getByRole('button', { name: /edit idea/i }).first().click();
    await page.locator('#title').fill('Updated Title');
    await page.getByTestId('submit-button').evaluate((el: HTMLElement) => el.click());

    // Give the request a moment to fire
    await page.waitForTimeout(300);
    expect(putCalled).toBe(true);
  });

  test('modal title shows "Modifier" (update mode) not "Nouvelle Idée"', async ({ page }) => {
    await page.getByRole('button', { name: /edit idea/i }).first().click();
    await expect(page.getByRole('dialog').getByText(/modifier/i)).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Delete idea
// ---------------------------------------------------------------------------

test.describe('Delete idea', () => {
  test.beforeEach(goToDashboard);

  test('accepting the confirm dialog calls DELETE /ideas/{id}', async ({ page }) => {
    let deleteCalled = false;
    await page.route(`${API_URL}/ideas/1`, (route) => {
      if (route.request().method() === 'DELETE') deleteCalled = true;
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'deleted' }) });
    });

    // Auto-accept the window.confirm dialog
    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: /delete idea/i }).first().click();

    await page.waitForTimeout(300);
    expect(deleteCalled).toBe(true);
  });

  test('cancelling the confirm dialog does NOT call DELETE', async ({ page }) => {
    let deleteCalled = false;
    await page.route(`${API_URL}/ideas/**`, (route) => {
      if (route.request().method() === 'DELETE') deleteCalled = true;
      route.continue();
    });

    page.once('dialog', (dialog) => dialog.dismiss());
    await page.getByRole('button', { name: /delete idea/i }).first().click();

    await page.waitForTimeout(300);
    expect(deleteCalled).toBe(false);
  });

  test('after accepted delete the idea card is removed from the UI', async ({ page }) => {
    // Mock delete + the subsequent GET /ideas refresh without the deleted item
    const ideasAfterDelete = MOCK_IDEAS.filter((i) => i.id !== 1);
    await page.route(`${API_URL}/ideas/1`, (route) => {
      if (route.request().method() === 'DELETE') {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ message: 'deleted' }) });
      } else {
        route.continue();
      }
    });
    await page.route(`${API_URL}/ideas`, (route) => {
      if (route.request().method() === 'GET') {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ideasAfterDelete) });
      } else {
        route.continue();
      }
    });

    page.once('dialog', (dialog) => dialog.accept());
    await page.getByRole('button', { name: /delete idea/i }).first().click();

    await expect(page.getByText('Machine Learning')).not.toBeVisible({ timeout: 5_000 });
    await expect(page.getByText('Python Tips')).toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// Client-side search filter
// ---------------------------------------------------------------------------

test.describe('Client-side search', () => {
  test.beforeEach(goToDashboard);

  test('typing in the search box filters cards without calling GET /ideas again', async ({ page }) => {
    let extraGetIdeasCalled = false;
    // Override the existing route to detect extra GET /ideas calls
    await page.route(`${API_URL}/ideas`, (route) => {
      if (route.request().method() === 'GET') extraGetIdeasCalled = true;
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IDEAS) });
    });

    await page.getByPlaceholder('Search...').fill('Machine');

    // Only matching idea is visible
    await expect(page.getByText('Machine Learning')).toBeVisible();
    await expect(page.getByText('Python Tips')).not.toBeVisible();

    expect(extraGetIdeasCalled).toBe(false);
  });

  test('clearing the search box shows all ideas again', async ({ page }) => {
    await page.getByPlaceholder('Search...').fill('Machine');
    await expect(page.getByText('Python Tips')).not.toBeVisible();

    await page.getByPlaceholder('Search...').clear();
    await expect(page.getByText('Python Tips')).toBeVisible();
  });

  test('search matches against tags', async ({ page }) => {
    // "python" tag is on the Python Tips card
    await page.getByPlaceholder('Search...').fill('python');
    await expect(page.getByText('Python Tips')).toBeVisible();
    await expect(page.getByText('Machine Learning')).not.toBeVisible();
  });
});


// ---------------------------------------------------------------------------
// My Ideas / All Ideas toggle
// ---------------------------------------------------------------------------

test.describe('My Ideas toggle', () => {
  test('"My Ideas" radio triggers GET /user/ideas', async ({ page }) => {
    let userIdeasCalled = false;
    await page.route(`${API_URL}/user/ideas`, (route) => {
      userIdeasCalled = true;
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER_IDEAS) });
    });
    await mockGetIdeas(page);

    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/dashboard');
    await page.waitForURL('/dashboard');

    await page.locator('label[for="myIdeas"]').click();

    await page.waitForTimeout(300);
    expect(userIdeasCalled).toBe(true);
  });

  test('"My Ideas" hides ideas not owned by the user', async ({ page }) => {
    await page.route(`${API_URL}/user/ideas`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER_IDEAS) })
    );
    await mockGetIdeas(page);

    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/dashboard');
    await page.waitForURL('/dashboard');

    await page.locator('label[for="myIdeas"]').click();

    // Only user's idea is shown
    await expect(page.getByText('Machine Learning')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Python Tips')).not.toBeVisible();
  });

  test('"All Ideas" radio after "My Ideas" calls GET /ideas', async ({ page }) => {
    await page.route(`${API_URL}/user/ideas`, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_USER_IDEAS) })
    );
    let allIdeasCallCount = 0;
    await page.route(`${API_URL}/ideas`, (route) => {
      allIdeasCallCount++;
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_IDEAS) });
    });

    await page.goto('/');
    await setAuthToken(page);
    await page.goto('/dashboard');
    await page.waitForURL('/dashboard');

    // Switch to My Ideas, then back to All Ideas
    await page.locator('label[for="myIdeas"]').click();
    await page.waitForTimeout(200);
    await page.locator('label[for="allIdeas"]').click();
    await page.waitForTimeout(300);

    // First GET was on mount, second is after toggling back
    expect(allIdeasCallCount).toBeGreaterThanOrEqual(2);
  });
});


// ---------------------------------------------------------------------------
// Similar ideas
// ---------------------------------------------------------------------------

test.describe('Similar ideas', () => {
  test.beforeEach(goToDashboard);

  test('"Similar" button is disabled when search input is empty', async ({ page }) => {
    await expect(page.getByRole('button', { name: /similar/i })).toBeDisabled();
  });

  test('"Similar" button is enabled when search input has text', async ({ page }) => {
    await page.getByPlaceholder('Search...').fill('neural');
    await expect(page.getByRole('button', { name: /similar/i })).toBeEnabled();
  });

  test('clicking "Similar" calls GET /ideas/similar/{term} and replaces the list', async ({ page }) => {
    const similarResults = [
      { id: 1, title: 'Machine Learning', content: 'Gradient descent', tags: 'ml', book_id: 1 },
    ];
    await mockGetSimilarIdeas(page, similarResults);

    await page.getByPlaceholder('Search...').fill('neural networks');
    await page.getByRole('button', { name: /similar/i }).click();

    // Similar results replace the full list
    await expect(page.getByText('Machine Learning')).toBeVisible({ timeout: 3_000 });
    await expect(page.getByText('Python Tips')).not.toBeVisible();
  });
});
