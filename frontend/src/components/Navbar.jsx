import React from 'react';
import { Menu, Sun, Moon, Shield, Radio, Sparkles } from 'lucide-react';

export default function Navbar({ onMenuToggle, darkMode, setDarkMode, activeBookingState }) {
  return (
    <header className="h-16 glass-panel border-b border-black/5 dark:border-white/10 px-4 lg:px-8 flex items-center justify-between sticky top-0 z-30 transition-colors">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuToggle}
          className="lg:hidden p-2 text-zinc-600 dark:text-zinc-300 hover:bg-black/5 dark:hover:bg-white/10 rounded-xl cursor-pointer transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 backdrop-blur-md">
            <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-500" />
            Backend Active
          </span>
          {activeBookingState && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 animate-pulse backdrop-blur-md">
              Automation: {activeBookingState.stage}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Modern Theme Toggle Pill */}
        <button
          onClick={() => setDarkMode(!darkMode)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold bg-black/5 dark:bg-white/10 hover:bg-black/10 dark:hover:bg-white/20 border border-black/5 dark:border-white/10 text-zinc-700 dark:text-zinc-200 transition-all cursor-pointer shadow-xs"
          title={`Switch to ${darkMode ? 'Light' : 'Dark'} Mode`}
        >
          {darkMode ? (
            <>
              <Sun className="w-4 h-4 text-amber-400 animate-spin-slow" />
              <span>Light Mode</span>
            </>
          ) : (
            <>
              <Moon className="w-4 h-4 text-indigo-600" />
              <span>Dark Mode</span>
            </>
          )}
        </button>

        <div className="hidden sm:flex items-center gap-2 pl-3 border-l border-black/5 dark:border-white/10 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          <Shield className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          <span>Local Personal Mode</span>
        </div>
      </div>
    </header>
  );
}
