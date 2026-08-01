import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Diasporic Memory · source annotation',
  description: 'Post-war visits to Germany — source-by-source review',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // The chrome is LTR; each text pane sets its own dir. Setting direction on
  // the pane element (not via CSS) is what makes selection and caret behaviour
  // correct inside the Hebrew pane.
  return (
    <html lang="en" dir="ltr">
      <body>{children}</body>
    </html>
  );
}
