import { expect, afterEach, vi } from 'vitest';
import React from 'react';
import { cleanup } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';

// Extend expect with Jest DOM matchers
expect.extend(matchers);

// Clean up after each test
afterEach(() => {
  cleanup();
});

// Mock global CSS modules
globalThis.vi = vi;
vi.mock('*.css', () => ({}));
vi.mock('*.scss', () => ({}));

// Mock global Tailwind CSS
vi.mock('tailwindcss', () => ({}));

// Mock global PostCSS
vi.mock('postcss', () => ({}));

// Mock global autoprefixer
vi.mock('autoprefixer', () => ({}));

// Mock global React Router
vi.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }) => children,
  MemoryRouter: ({ children }) => children,
  Routes: ({ children }) => children,
  Route: ({ children }) => children,
  Navigate: () => null,
  Link: ({ to, children }) => React.createElement('a', { href: to }, children),
  useNavigate: () => vi.fn(),
  useParams: () => ({}),
  useLocation: () => ({ pathname: '/' }),
}));

// Mock global Axios
vi.mock('axios', () => ({
  create: () => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() }
    }
  })
}));

// Mock Lucide React icons — return null (valid React child, avoids SVGSVGElement errors in React 19)
vi.mock('lucide-react', () => ({
  __esModule: true,
  default:       () => null,
  Plus:          () => null,
  X:             () => null,
  Menu:          () => null,
  Lightbulb:     () => null,
  User:          () => null,
  Search:        () => null,
  Home:          () => null,
  Settings:      () => null,
  LogOut:        () => null,
  Tag:           () => null,
  Edit:          () => null,
  Trash2:        () => null,
  Check:         () => null,
  Loader2:       () => null,
  ChevronDown:   () => null,
  ChevronUp:     () => null,
  ChevronRight:  () => null,
  ChevronLeft:   () => null,
  BookOpen:      () => null,
  Edit3:         () => null,
  ArrowLeft:     () => null,
  RotateCcw:     () => null,
  UserPlus:      () => null,
  UserMinus:     () => null,
}));

// Mock localStorage
const localStorageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] || null,
    setItem: (key, value) => {
      store[key] = value.toString();
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

Object.defineProperty(window, 'sessionStorage', {
  value: localStorageMock,
});

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock resizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
  root: null,
  rootMargin: '',
  thresholds: [],
}));

// Mock requestAnimationFrame
global.requestAnimationFrame = vi.fn().mockImplementation((cb) => setTimeout(cb, 0));
global.cancelAnimationFrame = vi.fn().mockImplementation((id) => clearTimeout(id));

// Mock performance.now
global.performance = {
  now: vi.fn().mockReturnValue(Date.now()),
};

// Mock console.error to ignore specific warnings
const originalError = console.error;
console.error = (...args) => {
  // Ignore specific warnings that are not important for testing
  const ignorePatterns = [
    /Warning: ReactDOM.render is no longer supported in React 18/,
    /Warning: Each child in a list should have a unique "key" prop/,
  ];
  
  const shouldIgnore = ignorePatterns.some(pattern => pattern.test(args.join(' ')));
  if (!shouldIgnore) {
    originalError(...args);
  }
};

export {};
