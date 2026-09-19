import React from 'react';

export default function StatusBadge({ status }) {
  const map = {
    CONFIRMED: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    COMPLETED: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    IN_PROGRESS: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 animate-pulse',
    WAITING_MANUAL: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 animate-bounce',
    PAYMENT_PENDING: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20 font-semibold',
    FAILED: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',
    CANCELLED: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border-slate-500/20',
    INITIATED: 'bg-sky-500/10 text-sky-600 dark:text-sky-400 border-sky-500/20',
  };

  const style = map[status] || 'bg-gray-500/10 text-gray-500 border-gray-500/20';

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${style}`}>
      {status || 'UNKNOWN'}
    </span>
  );
}
