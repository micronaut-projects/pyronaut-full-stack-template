// Email CSS must be inline: no stylesheet link, no utility classes. These are
// the same constraints React Email works under, so the upstream template's
// components port across closely.
export const page = {
  margin: 0,
  padding: '24px',
  backgroundColor: '#f4f6f8',
  fontFamily: "'Helvetica Neue', Helvetica, Arial, sans-serif",
  color: '#12161c',
};

export const card = {
  maxWidth: '560px',
  margin: '0 auto',
  padding: '32px',
  backgroundColor: '#ffffff',
  borderRadius: '6px',
  border: '1px solid #d7dee6',
};

export const heading = {
  margin: '0 0 16px',
  fontSize: '20px',
  lineHeight: 1.3,
  fontWeight: 600,
};

export const paragraph = { margin: '0 0 16px', fontSize: '15px', lineHeight: 1.6 };

export const button = {
  display: 'inline-block',
  padding: '11px 20px',
  backgroundColor: '#0d6b76',
  color: '#ffffff',
  borderRadius: '4px',
  fontSize: '15px',
  fontWeight: 600,
  textDecoration: 'none',
};

export const code = {
  display: 'inline-block',
  padding: '2px 6px',
  backgroundColor: '#e9edf2',
  borderRadius: '3px',
  fontFamily: "'SFMono-Regular', Consolas, monospace",
  fontSize: '14px',
};

export const footer = {
  margin: '24px 0 0',
  fontSize: '13px',
  lineHeight: 1.5,
  color: '#717d8c',
};
