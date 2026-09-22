import React from 'react';
import { EmailLayout } from './Layout';
import { button, heading, paragraph } from './styles';

export function ResetPasswordEmail({ projectName, username, link, validHours }) {
  return (
    <EmailLayout projectName={projectName} preview={`Reset your ${projectName} password`}>
      <h1 style={heading}>Password recovery</h1>
      <p style={paragraph}>
        We received a request to reset the password for <strong>{username}</strong>.
      </p>
      <p style={paragraph}>
        <a href={link} style={button}>
          Reset password
        </a>
      </p>
      <p style={paragraph}>
        The link is valid for {validHours} hours. If you did not request a password reset, you can
        ignore this email — nothing has changed.
      </p>
    </EmailLayout>
  );
}
