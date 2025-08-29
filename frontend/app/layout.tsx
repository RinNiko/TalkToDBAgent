import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Talk to DB - AI Database Assistant',
  description: 'Talk to your databases using natural language with AI',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className}`}>
        <div className="min-h-screen bg-gray-50 text-gray-900 dark:bg-[#0b0f14] dark:text-gray-100">
          {children}
        </div>
        <script
          dangerouslySetInnerHTML={{
            __html: `
(function(){
  try {
    var key='ttdb_theme';
    var saved = localStorage.getItem(key);
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    var isDark = saved ? saved === 'dark' : prefersDark;
    var root = document.documentElement;
    if (root) {
      if (isDark) root.classList.add('dark'); else root.classList.remove('dark');
    }
    window.__setTTDBTheme = function(theme){
      try { localStorage.setItem(key, theme); } catch(e){}
      var root = document.documentElement;
      if (!root) return;
      if (theme === 'dark') root.classList.add('dark'); else root.classList.remove('dark');
    }
  } catch(e){}
})();
`}}
        />
      </body>
    </html>
  );
}
