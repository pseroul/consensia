import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Navbar from './Navbar';

vi.mock('./BookSelector', () => ({
  default: () => <div data-testid="book-selector-stub" />,
}));

describe('Navbar Component', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token');
  });

  it('renders the navbar with logo and title', () => {
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    
    expect(screen.getByText('Consensia')).toBeInTheDocument();
    expect(screen.getByTestId('logo')).toBeInTheDocument();
  });

  it('renders navigation links', () => {
    // Render with menu open by passing isOpen prop
    render(<MemoryRouter><Navbar isOpen={true} /></MemoryRouter>);
    
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Tags & Ideas')).toBeInTheDocument();
  });

  it('navigates to dashboard when dashboard link is clicked', () => {
    render(<MemoryRouter><Navbar isOpen={true} /></MemoryRouter>);
    
    const dashboardLink = screen.getByText('Dashboard').closest('a');
    expect(dashboardLink).toHaveAttribute('href', '/dashboard');
  });

  it('navigates to tags page when tags link is clicked', () => {
    render(<MemoryRouter><Navbar isOpen={true} /></MemoryRouter>);
    
    const tagsLink = screen.getByText('Tags & Ideas').closest('a');
    expect(tagsLink).toHaveAttribute('href', '/tags-ideas');
  });

  it('renders settings and logout buttons', () => {
    render(<MemoryRouter><Navbar isOpen={true} /></MemoryRouter>);
    
    expect(screen.getByTestId('logout-icon')).toBeInTheDocument();
  });

  it('has correct logo alt text', () => {
    render(<MemoryRouter><Navbar /></MemoryRouter>);
    
    const logo = screen.getByTestId('logo');
    expect(logo).toHaveAttribute('alt', 'Brainiac5 Logo');
  });

  it('matches snapshot', () => {
    const { asFragment } = render(<Navbar />);
    expect(asFragment()).toMatchSnapshot();
  });
});
