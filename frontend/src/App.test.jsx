import { render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router';

import { Alert, Field, NotFound, Page } from './components';

// NotFound renders a <Link>, so it needs a router in scope — the same context
// the App tree supplies in the browser and StaticRouter supplies on the server.
const inRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe('shared components', () => {
  it('renders a labelled field with a stable test id', () => {
    render(<Field id="email" label="Email" value="a@example.com" onChange={() => {}} />);
    expect(screen.getByLabelText('Email')).toBeDefined();
    expect(screen.getByTestId('email-input').value).toBe('a@example.com');
  });

  it('marks a field invalid when it carries an error', () => {
    render(<Field id="email" label="Email" value="" onChange={() => {}} error="Required" />);
    expect(screen.getByTestId('email-input').getAttribute('aria-invalid')).toBe('true');
    expect(screen.getByText('Required')).toBeDefined();
  });

  it('renders nothing for an empty alert', () => {
    const { container } = render(<Alert kind="error">{null}</Alert>);
    expect(container.firstChild).toBeNull();
  });

  it('announces errors assertively', () => {
    render(<Alert kind="error">Incorrect email or password</Alert>);
    expect(screen.getByRole('alert').textContent).toBe('Incorrect email or password');
  });

  it('renders a page heading and actions', () => {
    render(<Page title="Items" actions={<span>action</span>}>body</Page>);
    expect(screen.getByRole('heading', { name: 'Items' })).toBeDefined();
    expect(screen.getByText('action')).toBeDefined();
  });
});

describe('NotFound', () => {
  it('uses the supplied message', () => {
    inRouter(<NotFound message="Item not found" />);
    expect(screen.getByText('Item not found')).toBeDefined();
    expect(screen.getByRole('link', { name: 'Back to the dashboard' })).toBeDefined();
  });
});
