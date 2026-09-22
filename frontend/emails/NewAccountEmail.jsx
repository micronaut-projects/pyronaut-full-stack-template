import React from 'react';
import { EmailLayout } from './Layout';
import { button, code, heading, paragraph } from './styles';

export function NewAccountEmail({ projectName, username, password, link }) {
  return (
    <EmailLayout projectName={projectName} preview={`Your new ${projectName} account`}>
      <h1 style={heading}>Welcome to {projectName}</h1>
      <p style={paragraph}>An account has been created for you. Your details are:</p>
      <p style={paragraph}>
        Username: <span style={code}>{username}</span>
        <br />
        Password: <span style={code}>{password}</span>
      </p>
      <p style={paragraph}>Please change your password after signing in for the first time.</p>
      <p style={paragraph}>
        <a href={link} style={button}>
          Sign in
        </a>
      </p>
    </EmailLayout>
  );
}
