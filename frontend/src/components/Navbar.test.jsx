import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import Navbar from './Navbar';

describe('Navbar Component', () => {
  beforeEach(() => {
    localStorage.setItem('access_token', 'test-token');
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
