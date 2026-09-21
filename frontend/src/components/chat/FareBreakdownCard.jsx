import React from 'react';
import { IndianRupee, ShieldCheck, Check } from 'lucide-react';

export default function FareBreakdownCard({ data, onConfirmBooking }) {
  if (!data || !data.breakdown) {
    return null;
  }

  const breakdown = data.breakdown;

  return (
    <div className="mt-3 p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm w-full max-w-md">
      <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-bold text-xs mb-3">
        <IndianRupee className="w-4 h-4" />
        <span>Official IRCTC Fare Itemization</span>
      </div>

      <div className="space-y-2 text-xs divide-y divide-zinc-100 dark:divide-zinc-800">
        <div className="flex justify-between py-1 text-zinc-600 dark:text-zinc-400">
          <span>Base Ticket Fare ({data.passengers_count} Pax)</span>
          <span className="font-mono text-zinc-900 dark:text-white font-medium">
            ₹{breakdown.per_passenger_base * data.passengers_count}
          </span>
        </div>

        <div className="flex justify-between py-1 text-zinc-600 dark:text-zinc-400">
          <span>Reservation Charge</span>
          <span className="font-mono text-zinc-900 dark:text-white font-medium">
            ₹{breakdown.reservation_fee}
          </span>
        </div>

        <div className="flex justify-between py-1 text-zinc-600 dark:text-zinc-400">
          <span>Superfast Surcharge</span>
          <span className="font-mono text-zinc-900 dark:text-white font-medium">
            ₹{breakdown.superfast_charge}
          </span>
        </div>

        <div className="flex justify-between py-1 text-zinc-600 dark:text-zinc-400">
          <span>IRCTC Convenience Fee (Incl. GST)</span>
          <span className="font-mono text-zinc-900 dark:text-white font-medium">
            ₹{breakdown.irctc_convenience_fee}
          </span>
        </div>

        <div className="flex justify-between pt-2.5 text-sm font-bold text-zinc-900 dark:text-white">
          <span>Total Payable Amount</span>
          <span className="font-mono text-emerald-600 dark:text-emerald-400 text-base">
            ₹{data.total_fare}
          </span>
        </div>
      </div>

      {onConfirmBooking && (
        <button
          onClick={onConfirmBooking}
          className="mt-4 w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition-all cursor-pointer"
        >
          <Check className="w-4 h-4" /> Confirm & Proceed to Payment
        </button>
      )}
    </div>
  );
}
