import React from 'react';
import { card, footer, page } from './styles';

export function EmailLayout({ projectName, preview, children }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>{preview}</title>
      </head>
      <body style={page}>
        <div style={card}>
          {children}
          <p style={footer}>{projectName}</p>
        </div>
      </body>
    </html>
  );
}
