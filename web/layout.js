import './globals.css';

export const metadata = {
  title: 'CPS Engine — Hausa History AI',
  description:
    'CPS Engine is an AI-powered Hausa History Knowledge Graph and Digital Mallam.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="ha">
      <body>{children}</body>
    </html>
  );
    }
