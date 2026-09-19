import React from 'react';
import { AlertTriangle, CreditCard, ShieldCheck, CheckCircle2, PauseCircle, XCircle } from 'lucide-react';

export default function ManualActionModal({ state, onAction }) {
  if (!state || !state.is_paused) return null;

  const isPayment = state.status === 'PAYMENT_PENDING' || state.stage === 'PAYMENT_PENDING';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-amber-500/40 dark:border-amber-500/50 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className={`px-6 py-4 flex items-center gap-3 text-white ${isPayment ? 'bg-gradient-to-r from-purple-600 to-indigo-600' : 'bg-gradient-to-r from-amber-600 to-orange-600'}`}>
          {isPayment ? <CreditCard className="w-6 h-6 animate-pulse" /> : <AlertTriangle className="w-6 h-6 animate-bounce" />}
          <div>
            <h3 className="text-lg font-bold">
              {isPayment ? 'Manual Payment Handover' : 'Security Verification Required'}
            </h3>
            <p className="text-xs text-white/80">Ref: {state.booking_ref}</p>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-sm text-amber-900 dark:text-amber-200 leading-relaxed">
            <p className="font-semibold mb-1 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-amber-600 dark:text-amber-400" />
              Human-In-The-Loop Safety Gate
            </p>
            <p>{state.manual_prompt || 'Please complete the manual verification step in the visible browser window.'}</p>
          </div>

          <div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
            <p>1. Switch to the official IRCTC / Bank browser window.</p>
            <p>2. Complete the CAPTCHA, OTP, or authentic payment step.</p>
            <p>3. Once finished, click <strong>"Continue"</strong> below to record confirmation.</p>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 bg-zinc-50 dark:bg-zinc-800/50 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between gap-2">
          <button
            onClick={() => onAction('cancel')}
            className="px-3.5 py-2 text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg transition-colors flex items-center gap-1.5"
          >
            <XCircle className="w-4 h-4" />
            Cancel Booking
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onAction('pause')}
              className="px-3.5 py-2 text-xs font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-lg transition-colors flex items-center gap-1.5"
            >
              <PauseCircle className="w-4 h-4" />
              Pause
            </button>
            <button
              onClick={() => onAction('continue')}
              className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-md shadow-emerald-600/20 transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
              {isPayment ? 'Payment Done, Continue' : 'Done, Continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
