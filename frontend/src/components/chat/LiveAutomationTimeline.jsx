import React from 'react';
import { CheckCircle2, Circle, Clock, Loader2, Sparkles, Terminal } from 'lucide-react';

export default function LiveAutomationTimeline({ currentStage = 'IDLE', logs = [] }) {
  const STAGES = [
    { id: 'SEARCHING_TRAINS', label: 'Search Trains & Availabilities' },
    { id: 'SELECTING_TRAIN', label: 'Select Train & Class' },
    { id: 'CALCULATING_FARE', label: 'Official Fare Itemization' },
    { id: 'PASSENGER_INPUT', label: 'Passenger Autofill & Preferences' },
    { id: 'PAYMENT_PENDING', label: 'Live IRCTC UPI QR Generation' },
    { id: 'CONFIRMED', label: 'Ticket Confirmed & PDF Ready' },
  ];

  const getStageStatus = (stageId) => {
    const stageOrder = STAGES.map((s) => s.id);
    const currentIndex = stageOrder.indexOf(currentStage);
    const thisIndex = stageOrder.indexOf(stageId);

    if (currentStage === 'CONFIRMED') return 'DONE';
    if (thisIndex < currentIndex) return 'DONE';
    if (thisIndex === currentIndex) return 'ACTIVE';
    return 'PENDING';
  };

  return (
    <div className="p-4 rounded-3xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-sm flex flex-col h-full">
      <div className="flex items-center justify-between pb-3 border-b border-zinc-100 dark:border-zinc-800">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-500 animate-pulse" />
          <h3 className="font-bold text-xs uppercase tracking-wider text-zinc-700 dark:text-zinc-300">
            IRCTC Live Automation Radar
          </h3>
        </div>
        <span className="flex items-center gap-1.5 text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/40 px-2 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
          STREAMING
        </span>
      </div>

      {/* Visual Timeline Steps */}
      <div className="mt-4 space-y-3">
        {STAGES.map((stage, idx) => {
          const status = getStageStatus(stage.id);

          return (
            <div key={stage.id} className="flex items-start gap-3">
              <div className="flex flex-col items-center">
                {status === 'DONE' && (
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                )}
                {status === 'ACTIVE' && (
                  <Loader2 className="w-4 h-4 text-emerald-500 animate-spin shrink-0" />
                )}
                {status === 'PENDING' && (
                  <Circle className="w-4 h-4 text-zinc-300 dark:text-zinc-700 shrink-0" />
                )}

                {idx < STAGES.length - 1 && (
                  <div
                    className={`w-0.5 h-6 my-1 transition-colors ${
                      status === 'DONE'
                        ? 'bg-emerald-500'
                        : status === 'ACTIVE'
                        ? 'bg-emerald-500/50'
                        : 'bg-zinc-200 dark:bg-zinc-800'
                    }`}
                  />
                )}
              </div>

              <div className="pt-0.5">
                <p
                  className={`text-xs font-semibold ${
                    status === 'ACTIVE'
                      ? 'text-emerald-600 dark:text-emerald-400'
                      : status === 'DONE'
                      ? 'text-zinc-900 dark:text-zinc-200'
                      : 'text-zinc-400 dark:text-zinc-600'
                  }`}
                >
                  {stage.label}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Live Event Stream Terminal */}
      <div className="mt-auto pt-4 border-t border-zinc-100 dark:border-zinc-800">
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-zinc-400 mb-2">
          <Terminal className="w-3.5 h-3.5" /> Recent Automation Milestones
        </div>
        <div className="p-3 rounded-xl bg-zinc-950 text-[11px] font-mono text-zinc-300 space-y-1.5 max-h-36 overflow-y-auto">
          {logs && logs.length > 0 ? (
            logs.slice(-5).map((log, i) => (
              <div key={i} className="flex items-start gap-1.5 text-zinc-300 leading-tight">
                <span className="text-emerald-400 select-none">❯</span>
                <span>{log}</span>
              </div>
            ))
          ) : (
            <span className="text-zinc-500 italic">Listening for automation events...</span>
          )}
        </div>
      </div>
    </div>
  );
}
