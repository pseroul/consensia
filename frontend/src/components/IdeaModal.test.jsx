import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import IdeaModal from './IdeaModal';
import { useState } from 'react';

describe('IdeaModal Component', () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();
  
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock lucide-react icons
    vi.mock('lucide-react', () => ({
      X: () => <svg data-testid="x-icon" />,
      Tag: () => <svg data-testid="tag-icon" />,
      Loader2: () => <svg data-testid="loader-icon" />,
    }));
  });

  it('renders the modal when isOpen is true', () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Nouvelle Idée')).toBeInTheDocument();
  });

  it('does not render the modal when isOpen is false', () => {
    render(<IdeaModal isOpen={false} onClose={mockOnClose} onSave={mockOnSave} />);
    
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes the modal when close button is clicked', () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);
    
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('closes the modal when overlay is clicked', () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const overlay = screen.getByTestId('modal-overlay');
    fireEvent.click(overlay);
    
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('prevents overlay click from closing modal when clicking on content', () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const content = screen.getByRole('dialog');
    fireEvent.click(content);
    
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('displays form fields for title, content, and tags', () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    expect(screen.getByLabelText('Title')).toBeInTheDocument();
    expect(screen.getByLabelText('Content')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Ajouter un tag...')).toBeInTheDocument();
  });

  it('calls onSave when form is submitted', async () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const titleInput = screen.getByLabelText('Title');
    const contentInput = screen.getByLabelText('Content');
    
    // Fill form fields
    fireEvent.change(titleInput, { target: { value: 'Test Idea' } });
    fireEvent.change(contentInput, { target: { value: 'Test Content' } });
    
    const form = screen.getByRole('form');
    fireEvent.submit(form);
    
    // Verify onSave was called with some data
    expect(mockOnSave).toHaveBeenCalledTimes(1);
    const savedData = mockOnSave.mock.calls[0][0];
    expect(savedData).toHaveProperty('title');
    expect(savedData).toHaveProperty('content');
    expect(savedData).toHaveProperty('tags');
  });

  it('shows submit button', () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const submitButton = screen.getByText('Save');
    expect(submitButton).toBeInTheDocument();
  });

  it('enables submit button when title and content are filled', () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const titleInput = screen.getByLabelText('Title');
    const contentInput = screen.getByLabelText('Content');
    const submitButton = screen.getByText('Save');
    
    fireEvent.change(titleInput, { target: { value: 'Test Idea' } });
    fireEvent.change(contentInput, { target: { value: 'Test Content' } });
    
    expect(submitButton).not.toBeDisabled();
  });

  it('clears form when modal is closed', () => {
    const { rerender } = render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const titleInput = screen.getByLabelText('Title');
    const contentInput = screen.getByLabelText('Content');
    
    fireEvent.change(titleInput, { target: { value: 'Test Idea' } });
    fireEvent.change(contentInput, { target: { value: 'Test Content' } });
    
    // Close the modal
    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);
    
    // Reopen the modal
    rerender(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);
    
    const newTitleInput = screen.getByLabelText('Title');
    const newContentInput = screen.getByLabelText('Content');
    
    expect(newTitleInput).toHaveValue('');
    expect(newContentInput).toHaveValue('');
  });
});
