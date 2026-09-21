import React from 'react';
import { Train, Clock, ArrowRight, CheckCircle2, AlertCircle } from 'lucide-react';

export default function TrainResultsCard({ data, onSelectClass, onBookTrain }) {
  if (!data || !data.trains || data.trains.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 space-y-3 w-full max-w-2xl">
      <div className="flex items-center justify-between text-xs font-semibold text-zinc-500 dark:text-zinc-400 px-1">
        <span>Available Trains ({data.trains.length})</span>
        <span>Route: {data.origin} ➔ {data.destination}</span>
      </div>

      {data.trains.map((train) => {
        const classes = train.classes || ['3A', '2A', 'SL'];
        const avlMap = train.classes_availability || {};

        return (
          <div
            key={train.train_number}
            className="p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800/80 shadow-sm hover:border-emerald-500/50 transition-all"
          >
            {/* Train Header */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-100 dark:border-zinc-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400 flex items-center justify-center font-bold text-xs">
                  <Train className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-zinc-900 dark:text-white flex items-center gap-2">
                    {train.train_name}
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400">
                      #{train.train_number}
                    </span>
                  </h4>
                </div>
              </div>

              <div className="flex items-center gap-3 text-xs font-medium text-zinc-500 dark:text-zinc-400">
                <span>{train.departure_time}</span>
                <span className="flex items-center gap-1 text-[11px] text-zinc-400">
                  <Clock className="w-3 h-3" /> {train.duration}
                </span>
                <span>{train.arrival_time}</span>
              </div>
            </div>

            {/* Class Chips & Booking Options */}
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {classes.map((cls) => {
                const avlInfo = avlMap[cls] || { status: 'AVAILABLE', fare: 1180.0 };
                const isAvail = avlInfo.status.includes('AVAILABLE');

                return (
                  <button
                    key={cls}
                    onClick={() => {
                      if (onSelectClass) onSelectClass(train, cls, avlInfo);
                    }}
                    className="flex-1 min-w-[120px] p-2.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-950/50 hover:bg-emerald-50/50 dark:hover:bg-emerald-950/30 hover:border-emerald-500/40 text-left transition-all group cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-zinc-800 dark:text-zinc-200 group-hover:text-emerald-500">
                        {cls}
                      </span>
                      <span className="font-mono font-bold text-xs text-zinc-900 dark:text-white">
                        ₹{avlInfo.fare}
                      </span>
                    </div>

                    <div className="mt-1 flex items-center gap-1 text-[11px]">
                      {isAvail ? (
                        <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> {avlInfo.status}
                        </span>
                      ) : (
                        <span className="text-amber-600 dark:text-amber-400 font-semibold flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> {avlInfo.status}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>

            {/* Fast Quick-Book CTA */}
            {onBookTrain && (
              <div className="mt-3 pt-2.5 border-t border-zinc-100 dark:border-zinc-800/60 flex justify-end">
                <button
                  onClick={() => onBookTrain(train)}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-1.5 shadow-sm transition-all cursor-pointer"
                >
                  Book This Train <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
