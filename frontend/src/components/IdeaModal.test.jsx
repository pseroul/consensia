import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('./ImpactComments', () => ({ default: () => null }));

import IdeaModal from './IdeaModal';

describe('IdeaModal Component', () => {
  const mockOnClose = vi.fn();
  const mockOnSave = vi.fn();
  
  beforeEach(() => {
    vi.clearAllMocks();
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

    // Close the modal (parent controls isOpen)
    rerender(<IdeaModal isOpen={false} onClose={mockOnClose} onSave={mockOnSave} />);

    // Reopen the modal — useEffect re-fires because isOpen changed
    rerender(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);

    const newTitleInput = screen.getByLabelText('Title');
    const newContentInput = screen.getByLabelText('Content');

    expect(newTitleInput).toHaveValue('');
    expect(newContentInput).toHaveValue('');
  });

  // ---------------------------------------------------------------------------
  // Tag logic tests
  // ---------------------------------------------------------------------------

  it('renders tag chips from semicolon-separated initialData.tags', () => {
    render(
      <IdeaModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        initialData={{ title: 'T', content: 'C', tags: 'ml;python' }}
      />
    );

    expect(screen.getByText('#ml')).toBeInTheDocument();
    expect(screen.getByText('#python')).toBeInTheDocument();
  });

  it('adds a tag chip when Enter is pressed in the tag input', async () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);

    const tagInput = screen.getByPlaceholderText('Ajouter un tag...');
    await userEvent.type(tagInput, 'newtag');
    fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

    expect(screen.getByText('#newtag')).toBeInTheDocument();
    expect(tagInput).toHaveValue('');
  });

  it('does not add a duplicate tag', async () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);

    const tagInput = screen.getByPlaceholderText('Ajouter un tag...');
    await userEvent.type(tagInput, 'dup');
    fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });
    await userEvent.type(tagInput, 'dup');
    fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

    const chips = screen.getAllByText('#dup');
    expect(chips).toHaveLength(1);
  });

  it('removes a tag chip when its × button is clicked', async () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);

    const tagInput = screen.getByPlaceholderText('Ajouter un tag...');
    await userEvent.type(tagInput, 'removeme');
    fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

    expect(screen.getByText('#removeme')).toBeInTheDocument();

    // The × button is inside the chip span — click the only remove button
    const removeButton = screen.getByText('#removeme').parentElement.querySelector('button');
    fireEvent.click(removeButton);

    expect(screen.queryByText('#removeme')).not.toBeInTheDocument();
  });

  it('serializes tags as semicolon-joined string in the onSave payload', async () => {
    render(<IdeaModal isOpen={true} onClose={mockOnClose} onSave={mockOnSave} />);

    const titleInput = screen.getByLabelText('Title');
    const contentInput = screen.getByLabelText('Content');
    const tagInput = screen.getByPlaceholderText('Ajouter un tag...');

    fireEvent.change(titleInput, { target: { value: 'My Idea' } });
    fireEvent.change(contentInput, { target: { value: 'Some content' } });

    await userEvent.type(tagInput, 'alpha');
    fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });
    await userEvent.type(tagInput, 'beta');
    fireEvent.keyDown(tagInput, { key: 'Enter', code: 'Enter' });

    fireEvent.submit(screen.getByRole('form'));

    expect(mockOnSave).toHaveBeenCalledWith(
      expect.objectContaining({ tags: 'alpha;beta' })
    );
  });

  it('prefills title and content in edit mode (initialData provided)', () => {
    render(
      <IdeaModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        initialData={{ title: 'Existing Idea', content: 'Existing content', tags: '' }}
      />
    );

    expect(screen.getByLabelText('Title')).toHaveValue('Existing Idea');
    expect(screen.getByLabelText('Content')).toHaveValue('Existing content');
    expect(screen.getByText("Modifier l\u2019id\u00e9e")).toBeInTheDocument();
  });

  it('shows Update button (not Save) in edit mode', () => {
    render(
      <IdeaModal
        isOpen={true}
        onClose={mockOnClose}
        onSave={mockOnSave}
        initialData={{ title: 'T', content: 'C', tags: '' }}
      />
    );

    expect(screen.getByText('Update')).toBeInTheDocument();
    expect(screen.queryByText('Save')).not.toBeInTheDocument();
  });
});
