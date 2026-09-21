import React, { useState, useEffect } from 'react';
import { QrCode, Clock, Copy, CheckCircle2, ShieldCheck, X } from 'lucide-react';

export default function LivePaymentQRModal({ qrPath, qrBase64, amount = 0, onClose, onPaid }) {
  const [timeLeft, setTimeLeft] = useState(300); // 5 minutes timer
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (timeLeft <= 0) return;
    const timer = setInterval(() => setTimeLeft((prev) => prev - 1), 1000);
    return () => clearInterval(timer);
  }, [timeLeft]);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;

  const handleCopy = () => {
    navigator.clipboard.writeText('irctc.official@upi');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const imageSrc = qrBase64 
    ? `data:image/png;base64,${qrBase64}` 
    : (qrPath ? (qrPath.startsWith('http') ? qrPath : `/api/logs/download?path=${encodeURIComponent(qrPath)}`) : null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-6 max-w-sm w-full shadow-2xl relative">
        {onClose && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}

        <div className="text-center">
          <div className="w-12 h-12 rounded-2xl bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 mx-auto flex items-center justify-center mb-3">
            <QrCode className="w-6 h-6" />
          </div>
          <h3 className="font-bold text-lg text-zinc-900 dark:text-white">Official IRCTC UPI QR</h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            Scan using GPay, PhonePe, or Paytm
          </p>
        </div>

        {/* QR Code Container */}
        <div className="mt-4 p-4 rounded-2xl bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 flex flex-col items-center">
          {imageSrc ? (
            <img
              src={imageSrc}
              alt="IRCTC Payment QR"
              className="w-52 h-52 object-contain rounded-xl bg-white p-2 shadow-inner"
            />
          ) : (
            <div className="w-52 h-52 flex flex-col items-center justify-center border-2 border-dashed border-zinc-300 dark:border-zinc-700 rounded-xl">
              <QrCode className="w-12 h-12 text-zinc-400 animate-pulse mb-2" />
              <span className="text-xs text-zinc-500 font-medium">Loading QR from IRCTC...</span>
            </div>
          )}

          {/* Amount Badge */}
          <div className="mt-3 flex items-center justify-between w-full px-2">
            <span className="text-xs text-zinc-500">Payable Amount:</span>
            <span className="font-mono font-bold text-base text-emerald-600 dark:text-emerald-400">
              ₹{amount}
            </span>
          </div>
        </div>

        {/* Countdown Timer */}
        <div className="mt-3 flex items-center justify-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
          <Clock className="w-4 h-4" />
          <span>Expires in: {minutes}:{seconds < 10 ? `0${seconds}` : seconds}</span>
        </div>

        {/* Actions */}
        <div className="mt-4 space-y-2">
          {onPaid && (
            <button
              onClick={onPaid}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-2 transition-all cursor-pointer shadow-sm"
            >
              <CheckCircle2 className="w-4 h-4" /> I Have Completed Payment
            </button>
          )}

          <button
            onClick={handleCopy}
            className="w-full py-2 rounded-xl border border-zinc-200 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 text-zinc-700 dark:text-zinc-300 text-xs font-medium flex items-center justify-center gap-1.5 transition-all cursor-pointer"
          >
            <Copy className="w-3.5 h-3.5" />
            {copied ? 'UPI ID Copied!' : 'Copy IRCTC Merchant UPI'}
          </button>
        </div>
      </div>
    </div>
  );
}
