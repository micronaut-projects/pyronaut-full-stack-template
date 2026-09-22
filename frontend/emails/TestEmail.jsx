import React from 'react';
import { EmailLayout } from './Layout';
import { heading, paragraph } from './styles';

export function TestEmail({ projectName, email }) {
  return (
    <EmailLayout projectName={projectName} preview={`${projectName} test email`}>
      <h1 style={heading}>Test email</h1>
      <p style={paragraph}>
        This is a test email from {projectName}, sent to {email}.
      </p>
      <p style={paragraph}>
        It was rendered from a React component on GraalJS, inside the same JVM that serves the
        API — no Node process, and no HTML compiled ahead of time.
      </p>
    </EmailLayout>
  );
}
