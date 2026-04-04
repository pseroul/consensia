import { expect, afterEach, beforeAll, afterAll, vi } from 'vitest';
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
  Routes: ({ children }) => children,
  Route: ({ children }) => children,
  Link: ({ to, children }) => {
    const link = document.createElement('a');
    link.href = to;
    link.textContent = children;
    return link;
  },
  useNavigate: () => vi.fn(),
  useParams: () => ({}),
  useLocation: () => ({}),
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

// Mock global Lucide React icons
vi.mock('lucide-react', () => ({
  __esModule: true,
  default: ({ size = 24, color = 'currentColor', ...props }) => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'icon');
    svg.setAttribute('width', size);
    svg.setAttribute('height', size);
    svg.setAttribute('fill', 'currentColor');
    Object.entries(props).forEach(([key, value]) => {
      svg.setAttribute(key, value);
    });
    return svg;
  },
  // Mock specific icons that are used
  Plus: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'plus-icon');
    return svg;
  },
  X: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'x-icon');
    return svg;
  },
  Search: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'search-icon');
    return svg;
  },
  Home: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'home-icon');
    return svg;
  },
  Settings: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'settings-icon');
    return svg;
  },
  LogOut: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'logout-icon');
    return svg;
  },
  Tag: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'tag-icon');
    return svg;
  },
  Edit: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'edit-icon');
    return svg;
  },
  Trash2: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'trash-icon');
    return svg;
  },
  Check: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'check-icon');
    return svg;
  },
  ChevronDown: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'chevron-down-icon');
    return svg;
  },
  ChevronUp: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'chevron-up-icon');
    return svg;
  },
  ChevronRight: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'chevron-right-icon');
    return svg;
  },
  ChevronLeft: () => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('data-testid', 'chevron-left-icon');
    return svg;
  },
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
