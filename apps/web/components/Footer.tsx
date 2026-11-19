import React from "react";
import Link from "next/link";
import { Lock, ShieldAlert, Cpu } from "lucide-react";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 py-8 text-xs text-slate-500">
      <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 font-medium text-slate-700 dark:text-slate-300">
            <Lock className="w-3.5 h-3.5 text-teal-600" />
            Zero Tracking • Zero AI Training • 60-min Hard Purge
          </span>
        </div>

        <div className="flex items-center gap-6">
          <Link href="/privacy" className="hover:underline">
            Privacy Policy
          </Link>
          <Link href="/how-it-works" className="hover:underline">
            Verification Engine
          </Link>
          <Link href="/limits" className="hover:underline">
            What Reaboard Can't Do
          </Link>
        </div>

        <p>© {new Date().getFullYear()} Reaboard. Open source & privacy verified.</p>
      </div>
    </footer>
  );
}
