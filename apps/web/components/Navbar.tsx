"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ShieldCheck, Moon, Sun, Globe } from "lucide-react";

export function Navbar({ locale = "en", onLocaleChange }: { locale?: string; onLocaleChange?: (l: string) => void }) {
  const [dark, setDark] = useState(false);

  const toggleTheme = () => {
    setDark(!dark);
    document.documentElement.classList.toggle("dark");
  };

  return (
    <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-bold text-xl tracking-tight text-teal-600 dark:text-teal-400">
          <ShieldCheck className="w-6 h-6" />
          <span>Reaboard</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600 dark:text-slate-300">
          <Link href="/how-it-works" className="hover:text-teal-600 dark:hover:text-teal-400 transition-colors">
            How it works
          </Link>
          <Link href="/privacy" className="hover:text-teal-600 dark:hover:text-teal-400 transition-colors">
            Privacy
          </Link>
          <Link href="/limits" className="hover:text-teal-600 dark:hover:text-teal-400 transition-colors">
            Known limits
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <button
            onClick={() => onLocaleChange?.(locale === "en" ? "id" : "en")}
            className="flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-md border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            title="Toggle language"
          >
            <Globe className="w-3.5 h-3.5" />
            <span>{locale.toUpperCase()}</span>
          </button>

          <button
            onClick={toggleTheme}
            className="p-2 rounded-md border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
            aria-label="Toggle theme"
          >
            {dark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-600" />}
          </button>
        </div>
      </div>
    </header>
  );
}
