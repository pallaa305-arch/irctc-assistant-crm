import React, { useState, useEffect } from 'react';
import { AlertTriangle, CreditCard, ShieldCheck, CheckCircle2, PauseCircle, XCircle, RefreshCw, Send, Image as ImageIcon, Clock } from 'lucide-react';

export default function ManualActionModal({ state, onAction }) {
  const [inputValue, setInputValue] = useState('');
  const [imgTimestamp, setImgTimestamp] = useState(Date.now());
  const [imgError, setImgError] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [countdown, setCountdown] = useState(180);

  const isPayment = state?.status === 'PAYMENT_PENDING' || state?.stage === 'PAYMENT_PENDING' || state?.waiting_input_type === 'PAYMENT';
  const isCaptcha = state?.waiting_input_type === 'CAPTCHA';
  const isOtp = state?.waiting_input_type === 'OTP';
  const isInputRequired = isCaptcha || isOtp;

  useEffect(() => {
    if (state?.is_paused) {
      setImgTimestamp(Date.now());
      setImgError(false);
      setInputValue('');
      setSubmitting(false);
    }
  }, [state?.booking_ref, state?.is_paused, state?.waiting_input_type]);

  useEffect(() => {
    if (isPayment) {
      const initial = state?.timer_remaining_seconds ?? (state?.timer_seconds ?? 180);
      setCountdown(initial);
      const timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [isPayment, state?.timer_remaining_seconds, state?.timer_seconds]);

  const formatCountdown = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (!state || !state.is_paused) return null;

  let modalTitle = 'Action Required: Train Selection / Verification';
  let headerGradient = 'bg-gradient-to-r from-emerald-600 to-teal-600';
  if (isPayment) {
    modalTitle = 'Payment Handover (UPI QR / NetBanking)';
    headerGradient = 'bg-gradient-to-r from-purple-600 to-indigo-600';
  } else if (isCaptcha) {
    modalTitle = 'Security Verification: Visual CAPTCHA';
    headerGradient = 'bg-gradient-to-r from-amber-600 to-orange-600';
  } else if (isOtp) {
    modalTitle = 'Security Verification: OTP Required';
    headerGradient = 'bg-gradient-to-r from-blue-600 to-cyan-600';
  }

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (isInputRequired && !inputValue.trim()) {
      alert('Kripya CAPTCHA text ya OTP darj karein.');
      return;
    }
    setSubmitting(true);
    try {
      await onAction('continue', inputValue.trim());
    } finally {
      setSubmitting(false);
    }
  };

  const handleQuickConfirm = async (val) => {
    setSubmitting(true);
    try {
      await onAction('continue', val);
    } finally {
      setSubmitting(false);
    }
  };

  const handleManualContinue = async () => {
    setSubmitting(true);
    try {
      await onAction('continue', null);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in overflow-y-auto">
      <div className="bg-white dark:bg-zinc-900 border border-amber-500/40 dark:border-amber-500/50 rounded-2xl shadow-2xl max-w-xl w-full overflow-hidden my-6">
        {/* Header */}
        <div className={`px-6 py-4 flex items-center justify-between text-white ${headerGradient}`}>
          <div className="flex items-center gap-3">
            {isPayment ? <CreditCard className="w-6 h-6 animate-pulse" /> : <AlertTriangle className="w-6 h-6 animate-bounce" />}
            <div>
              <h3 className="text-lg font-bold">
                {modalTitle}
              </h3>
              <p className="text-xs text-white/80">Booking Ref: {state.booking_ref}</p>
            </div>
          </div>
          <button
            onClick={() => setImgTimestamp(Date.now())}
            title="Refresh Live Screenshot"
            className="p-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-xs transition-colors flex items-center gap-1 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span className="text-[11px] hidden sm:inline">Refresh</span>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 space-y-5">
          {/* Safety Alert Banner */}
          <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-sm text-amber-900 dark:text-amber-200 leading-relaxed">
            <p className="font-semibold mb-1 flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
              Official IRCTC Safety Verification
            </p>
            <p className="text-xs sm:text-sm">{state.manual_prompt || 'Please complete the verification step below.'}</p>
          </div>

          {/* Live Browser Screenshot / CAPTCHA / QR Preview */}
          <div className="bg-zinc-100 dark:bg-zinc-800/80 rounded-xl border border-zinc-200 dark:border-zinc-700 p-3 text-center">
            <div className="flex items-center justify-between mb-2 text-xs font-semibold text-zinc-600 dark:text-zinc-300">
              <span className="flex items-center gap-1.5">
                <ImageIcon className="w-3.5 h-3.5 text-blue-500" />
                Live Screen Capture:
              </span>
              <button
                type="button"
                onClick={() => setImgTimestamp(Date.now())}
                className="text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 text-[11px] cursor-pointer"
              >
                <RefreshCw className="w-3 h-3" /> Reload Image
              </button>
            </div>

            <div className="bg-white dark:bg-zinc-900 rounded-lg p-2 flex items-center justify-center min-h-[120px] max-h-[260px] overflow-hidden border border-zinc-200 dark:border-zinc-700">
              {!imgError ? (
                <img
                  src={`/api/bookings/screenshot/${state.booking_ref}?t=${imgTimestamp}`}
                  alt="IRCTC CAPTCHA / Screen"
                  onError={() => setImgError(true)}
                  className="max-h-[240px] max-w-full object-contain rounded select-none shadow-sm"
                />
              ) : (
                <div className="py-6 text-xs text-zinc-400 space-y-1">
                  <p>Screenshot loading or browser window is visible in taskbar.</p>
                  <p className="text-[11px] text-zinc-500">Chrome window me bhi screen dekh sakte hain.</p>
                </div>
              )}
            </div>
          </div>

          {/* CAPTCHA / OTP Input Form */}
          {isInputRequired && (
            <form onSubmit={handleSubmit} className="space-y-3">
              {state.suggested_captcha && (
                <div className="flex items-center justify-between p-2.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 rounded-xl">
                  <span className="text-xs text-emerald-800 dark:text-emerald-300 font-medium">
                    ⚡ AI Auto-Detected: <strong className="font-mono tracking-wider text-sm">{state.suggested_captcha}</strong>
                  </span>
                  <button
                    type="button"
                    onClick={() => handleQuickConfirm(state.suggested_captcha)}
                    disabled={submitting}
                    className="px-3 py-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg shadow-xs cursor-pointer"
                  >
                    Confirm (1-Click)
                  </button>
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1.5">
                  Enter CAPTCHA / OTP Text:
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder={state.suggested_captcha || "Type CAPTCHA here..."}
                    autoFocus
                    className="flex-1 px-3.5 py-2.5 bg-zinc-50 dark:bg-zinc-800 border-2 border-emerald-500/60 focus:border-emerald-500 rounded-xl text-base font-bold text-zinc-900 dark:text-white tracking-widest uppercase outline-hidden"
                  />
                  <button
                    type="submit"
                    disabled={submitting || !inputValue.trim()}
                    className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-1.5 cursor-pointer"
                  >
                    <Send className="w-4 h-4" />
                    Submit
                  </button>
                </div>
              </div>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                💡 <strong>Tip:</strong> Aap yahan type karke Submit kar sakte hain, ya Telegram par photo dekh kar text reply kar sakte hain, ya sidhe Google Chrome me fill kar sakte hain.
              </p>
            </form>
          )}

          {isPayment && (
            <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 rounded-xl p-4 text-center space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-emerald-800 dark:text-emerald-300">
                  Official IRCTC Total Payable Amount:
                </span>
                <span className={`text-xs font-bold font-mono px-2.5 py-1 rounded-full flex items-center gap-1 shadow-xs ${countdown <= 30 ? 'bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300 animate-pulse' : 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'}`}>
                  <Clock className="w-3.5 h-3.5" />
                  Time Left: {formatCountdown(countdown)}
                </span>
              </div>
              <p className="text-2xl font-black text-emerald-600 dark:text-emerald-400">
                {state.fare ? `₹${Number(state.fare).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : 'As per Official IRCTC Portal'}
              </p>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                📱 Kisi bhi UPI app (GPay, PhonePe, Paytm) se QR code scan karke exact yahi amount pay karein. <strong>Payment transfer hote hi page automatically PNR confirm kar dega!</strong>
              </p>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 bg-zinc-50 dark:bg-zinc-800/50 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between gap-2">
          <button
            onClick={() => onAction('cancel')}
            className="px-3 py-2 text-xs font-medium text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
          >
            <XCircle className="w-4 h-4" />
            Cancel Booking
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onAction('pause')}
              className="px-3 py-2 text-xs font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <PauseCircle className="w-4 h-4" />
              Pause
            </button>
            <button
              onClick={handleManualContinue}
              disabled={submitting}
              className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg shadow-md transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
              {isPayment ? 'Payment Done, Continue' : 'Done in Browser, Continue'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
