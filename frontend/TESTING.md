# Testing Guide for Brainiac5 Frontend

This document provides an overview of the testing setup and best practices for testing the Brainiac5 frontend application.

## Testing Framework

The frontend uses **Vitest** as the testing framework, combined with **React Testing Library** for component testing and **MSW (Mock Service Worker)** for API mocking.

### Key Features

- **Vitest**: Fast, modern testing framework compatible with Vite
- **React Testing Library**: Encourages best practices for testing React components
- **MSW**: Mock API endpoints during testing
- **Jest DOM Matchers**: Extended matchers for DOM assertions
- **Coverage Reporting**: Built-in coverage reporting with 80% threshold

## Running Tests

### Basic Commands

```bash
# Run tests once
npm test

# Run tests in watch mode (re-runs on file changes)
npm run test:watch

# Run tests with coverage report
npm run test:coverage

# Run tests in CI mode (with coverage)
npm run test:ci
```

### Test Commands

- `npm test` - Run tests once
- `npm run test:watch` - Run tests in watch mode
- `npm run test:coverage` - Run tests with coverage report
- `npm run test:ci` - Run tests in CI mode

## Test Structure

Tests are organized alongside the components they test:

```
frontend/
├── src/
│   ├── components/
│   │   ├── Button/
│   │   │   ├── Button.jsx
│   │   │   ├── Button.test.jsx
│   │   │   └── Button.stories.jsx
│   │   └── ...
│   ├── pages/
│   │   ├── Dashboard/
│   │   │   ├── Dashboard.jsx
│   │   │   └── Dashboard.test.jsx
│   │   └── ...
│   └── ...
└── ...
```

## Writing Tests

### Basic Test Example

```jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Button from './Button';

describe('Button Component', () => {
  it('renders with correct text', () => {
    render(<Button>Click Me</Button>);
    
    expect(screen.getByText('Click Me')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click Me</Button>);
    
    fireEvent.click(screen.getByText('Click Me'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

### Common Testing Patterns

#### 1. Rendering Tests
```jsx
it('renders the component', () => {
  render(<MyComponent />);
  expect(screen.getByTestId('my-component')).toBeInTheDocument();
});
```

#### 2. Interaction Tests
```jsx
it('handles button click', () => {
  const handleClick = vi.fn();
  render(<Button onClick={handleClick}>Click</Button>);
  
  fireEvent.click(screen.getByText('Click'));
  expect(handleClick).toHaveBeenCalled();
});
```

#### 3. Form Tests
```jsx
it('submits form data', () => {
  const handleSubmit = vi.fn();
  render(<MyForm onSubmit={handleSubmit} />);
  
  const nameInput = screen.getByLabelText('Name');
  const submitButton = screen.getByText('Submit');
  
  fireEvent.change(nameInput, { target: { value: 'John' } });
  fireEvent.click(submitButton);
  
  expect(handleSubmit).toHaveBeenCalledWith({ name: 'John' });
});
```

#### 4. Async Tests
```jsx
it('loads data asynchronously', async () => {
  render(<DataComponent />);
  
  await waitFor(() => {
    expect(screen.getByText('Loaded Data')).toBeInTheDocument();
  });
});
```

#### 5. API Mocking with MSW
```jsx
import { setupWorker, rest } from 'msw';

const worker = setupWorker(
  rest.get('/api/data', (req, res, ctx) => {
    return res(ctx.json({ data: 'mocked data' }));
  })
);

beforeAll(() => worker.listen());
afterEach(() => worker.resetAll());
afterAll(() => worker.close());

it('fetches data from API', async () => {
  render(<DataComponent />);
  
  await waitFor(() => {
    expect(screen.getByText('mocked data')).toBeInTheDocument();
  });
});
```

## Test Setup

The `src/setupTests.js` file provides global test configuration:

- **Jest DOM Matchers**: Extended expect assertions for DOM elements
- **Mocks**: Global mocks for common dependencies (React Router, Axios, Icons, etc.)
- **Cleanup**: Automatic cleanup after each test
- **Browser APIs**: Mocked browser APIs (localStorage, matchMedia, etc.)

## Best Practices

### 1. Test Structure
- Use `describe` for component/test suite grouping
- Use `it` or `test` for individual test cases
- Keep tests focused on one behavior per test

### 2. Naming Conventions
- Test files should match component files: `Component.test.jsx`
- Use clear, descriptive test names
- Follow the pattern: "it should [behavior] when [condition]"

### 3. Assertions
- Use React Testing Library queries (`getBy`, `queryBy`, `findBy`)
- Prefer `getByRole` and `getByLabelText` over `getByTestId` when possible
- Use `toBeInTheDocument()` for existence checks

### 4. Mocking
- Mock external dependencies and APIs
- Keep mocks minimal and focused
- Use MSW for API mocking when possible

### 5. Async Testing
- Use `waitFor` for async operations
- Use `findBy` queries for elements that appear asynchronously
- Mock timers when testing time-based behavior

## Coverage

The project has a **80% coverage threshold** for:
- Lines
- Functions
- Branches
- Statements

To check coverage:
```bash
npm run test:coverage
```

## Debugging Tests

### Common Issues

1. **Component not rendering**: Check if all required props are provided
2. **Queries failing**: Use `screen.debug()` to inspect the DOM
3. **Async issues**: Use `waitFor` or `findBy` for async elements
4. **Mocking issues**: Verify mocks are set up correctly

### Debugging Tools

```jsx
// Debug the entire screen
screen.debug();

// Debug a specific element
const element = screen.getByTestId('my-element');
console.log(element);

// Pause test execution
vi.fn().mockImplementation(() => {
  debugger;
});
```

## CI/CD Integration

Tests are configured to run in CI environments with:
- Coverage reporting
- Strict failure on test failures
- Clean test environment

## Contributing

When adding new features or components:
1. Write tests for new functionality
2. Ensure test coverage meets thresholds
3. Add tests to existing test files or create new ones
4. Run tests locally before submitting PRs

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [MSW Documentation](https://mswjs.io/)
- [Jest DOM](https://github.com/testing-library/jest-dom)
