import React, { useState } from 'react';
import { ShieldAlert, ArrowRight, X } from 'lucide-react';

export default function CaptchaFallbackDrawer({ challengeType = 'CAPTCHA', imageSrc, onSubmit, onCancel }) {
  const [inputVal, setInputVal] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputVal.trim() && onSubmit) {
      onSubmit(inputVal.trim());
      setInputVal('');
    }
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 p-5 rounded-3xl bg-white dark:bg-zinc-900 border-2 border-emerald-500/80 shadow-2xl max-w-sm w-full animate-slide-up">
      <div className="flex items-center justify-between pb-3 border-b border-zinc-100 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-5 h-5 text-emerald-600 dark:text-emerald-400 animate-pulse" />
          <h4 className="font-bold text-sm text-zinc-900 dark:text-white">
            IRCTC {challengeType} Verification
          </h4>
        </div>
        {onCancel && (
          <button onClick={onCancel} className="text-zinc-400 hover:text-zinc-600">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
        IRCTC portal ne verification request kiya hai. Kripya dekh kar turant enter karein:
      </p>

      {imageSrc && (
        <div className="mt-3 p-2 bg-zinc-100 dark:bg-zinc-950 rounded-xl flex items-center justify-center border border-zinc-200 dark:border-zinc-800">
          <img
            src={imageSrc}
            alt="IRCTC Challenge"
            className="h-12 object-contain rounded-lg"
          />
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <input
          type="text"
          value={inputVal}
          onChange={(e) => setInputVal(e.target.value)}
          placeholder={challengeType === 'OTP' ? 'Enter 6-digit OTP' : 'Enter CAPTCHA letters'}
          autoFocus
          className="flex-1 px-3 py-2 rounded-xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 text-xs font-mono font-bold tracking-widest text-zinc-900 dark:text-white focus:outline-none focus:border-emerald-500"
        />
        <button
          type="submit"
          disabled={!inputVal.trim()}
          className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-xs flex items-center gap-1 shadow-sm transition-all cursor-pointer"
        >
          Submit <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}
