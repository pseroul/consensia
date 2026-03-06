import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Navbar from './Navbar';
import { useNavigate } from 'react-router-dom';

describe('Navbar Component', () => {
  let navigateMock;
  
  beforeEach(() => {
    navigateMock = vi.fn();
    
    // Mock react-router-dom
    vi.mock('react-router-dom', () => ({
      ...vi.importActual('react-router-dom'),
      useNavigate: () => navigateMock,
      Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
    }));
    
    // Mock lucide-react icons
    vi.mock('lucide-react', () => ({
      Menu: () => <svg data-testid="menu-icon" />,
      X: () => <svg data-testid="x-icon" />,
      LogOut: () => <svg data-testid="logout-icon" />,
      Lightbulb: () => <svg data-testid="logo" alt="Brainiac5 Logo" />,
      Home: () => <svg data-testid="home-icon" />,
      Settings: () => <svg data-testid="settings-icon" />,
      User: () => <svg data-testid="user-icon" />,
      Tag: () => <svg data-testid="tag-icon" />,
    }));
    
    // Mock localStorage to simulate authenticated user
    const localStorageMock = (() => {
      let store = {};
      return {
        getItem: (key) => store[key],
        setItem: (key, value) => { store[key] = value.toString(); },
        clear: () => { store = {}; },
      };
    })();
    
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
    });
    
    // Set authenticated state for tests
    localStorage.setItem('isAuthenticated', 'true');
  });

  it('renders the navbar with logo and title', () => {
    render(<Navbar />);
    
    expect(screen.getByText('Consensia')).toBeInTheDocument();
    expect(screen.getByTestId('logo')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    // Render with menu open by passing isOpen prop
    render(<Navbar isOpen={true} />);
    
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Tags & Ideas')).toBeInTheDocument();
  });

  it('navigates to dashboard when dashboard link is clicked', () => {
    render(<Navbar isOpen={true} />);
    
    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink).toHaveAttribute('href', '/dashboard');
  });

  it('navigates to tags page when tags link is clicked', () => {
    render(<Navbar isOpen={true} />);
    
    const tagsLink = screen.getByText('Tags & Ideas').closest('a');
    expect(tagsLink).toHaveAttribute('href', '/tags-ideas');
  });

  it('renders settings and logout buttons', () => {
    render(<Navbar isOpen={true} />);
    
    expect(screen.getByTestId('logout-icon')).toBeInTheDocument();
  });

  it('has correct logo alt text', () => {
    render(<Navbar />);
    
    const logo = screen.getByTestId('logo');
    expect(logo).toHaveAttribute('alt', 'Brainiac5 Logo');
  });

  it('matches snapshot', () => {
    const { asFragment } = render(<Navbar />);
    expect(asFragment()).toMatchSnapshot();
  });
});
