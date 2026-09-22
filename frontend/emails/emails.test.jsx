import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';

import { NewAccountEmail } from './NewAccountEmail';
import { ResetPasswordEmail } from './ResetPasswordEmail';
import { TestEmail } from './TestEmail';

// These components are rendered on GraalJS in production, by the same bundle
// that renders the pages. The assertions below are the contract the Python
// MailService depends on: see src/app/services/mail.py.
describe('email templates', () => {
  it('renders the test email with the project name and recipient', () => {
    const html = renderToStaticMarkup(
      <TestEmail projectName="Acme" email="someone@example.com" />
    );
    expect(html).toContain('Acme');
    expect(html).toContain('someone@example.com');
  });

  it('renders the new-account email with credentials and a sign-in link', () => {
    const html = renderToStaticMarkup(
      <NewAccountEmail
        projectName="Acme"
        username="someone@example.com"
        password="hunter2222"
        link="https://acme.example/"
      />
    );
    expect(html).toContain('someone@example.com');
    expect(html).toContain('hunter2222');
    expect(html).toContain('href="https://acme.example/"');
  });

  it('renders the reset email with the tokenised link and validity window', () => {
    const html = renderToStaticMarkup(
      <ResetPasswordEmail
        projectName="Acme"
        username="someone@example.com"
        link="https://acme.example/reset-password?token=abc"
        validHours={48}
      />
    );
    expect(html).toContain('token=abc');
    expect(html).toContain('48 hours');
  });

  it('inlines all styling — an email must carry no stylesheet link', () => {
    const html = renderToStaticMarkup(<TestEmail projectName="Acme" email="a@example.com" />);
    expect(html).not.toContain('<link');
    expect(html).toContain('style="');
  });
});
