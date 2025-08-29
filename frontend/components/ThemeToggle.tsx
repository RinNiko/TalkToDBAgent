"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle() {
  const [theme, setTheme] = useState<'light'|'dark'>('light');

  useEffect(() => {
    try {
      const saved = localStorage.getItem('ttdb_theme');
      const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const initial = (saved as 'light'|'dark'|null) || (prefersDark ? 'dark' : 'light');
      setTheme(initial);
    } catch {}
  }, []);

  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark';
    setTheme(next);
    try { (window as any).__setTTDBTheme && (window as any).__setTTDBTheme(next); } catch {}
  }

  return (
    <button onClick={toggle} className="inline-flex items-center rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 px-2.5 py-1 text-xs hover:bg-gray-50 dark:hover:bg-gray-700" title="Toggle theme">
      {theme === 'dark' ? (<><Sun className="h-4 w-4 mr-1"/>Light</>) : (<><Moon className="h-4 w-4 mr-1"/>Dark</>)}
    </button>
  );
}
