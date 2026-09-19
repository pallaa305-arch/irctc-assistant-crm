import React, { useState, useEffect } from 'react';
import { 
  Terminal, 
  RefreshCw, 
  ShieldCheck, 
  Filter, 
  Trash2, 
  Search
} from 'lucide-react';
import { fetchLogs } from '../services/api';

export default function Logs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [catFilter, setCatFilter] = useState('ALL');
  const [autoRefresh, setAutoRefresh] = useState(true);

  const loadLogs = async () => {
    try {
      const data = await fetchLogs({
        level: levelFilter,
        category: catFilter,
      });
      setLogs(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [levelFilter, catFilter]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(loadLogs, 3000);
    return () => clearInterval(interval);
  }, [autoRefresh, levelFilter, catFilter]);

  const levelColor = (level) => {
    switch (level) {
      case 'ERROR': return 'text-rose-500 bg-rose-500/10 border-rose-500/20';
      case 'WARNING': return 'text-amber-500 bg-amber-500/10 border-amber-500/20';
      default: return 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Structured Application Logs</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Real-time sanitized audit trail with zero credential leakage ({logs.length} events)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded text-emerald-600 focus:ring-emerald-500"
            />
            Auto-refresh (3s)
          </label>

          <button
            onClick={loadLogs}
            className="p-2 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-xl text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 bg-white dark:bg-zinc-900 p-3 rounded-2xl border border-zinc-200 dark:border-zinc-800 text-xs">
        <span className="font-semibold text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
          <Filter className="w-3.5 h-3.5" /> Filters:
        </span>
        <select
          value={levelFilter}
          onChange={(e) => setLevelFilter(e.target.value)}
          className="px-2.5 py-1.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white"
        >
          <option value="ALL">All Levels</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
        </select>

        <select
          value={catFilter}
          onChange={(e) => setCatFilter(e.target.value)}
          className="px-2.5 py-1.5 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white"
        >
          <option value="ALL">All Categories</option>
          <option value="AUTOMATION">AUTOMATION</option>
          <option value="CRM">CRM</option>
          <option value="NOTIFY">NOTIFY</option>
          <option value="SYSTEM">SYSTEM</option>
        </select>

        <div className="ml-auto text-[11px] text-zinc-400 flex items-center gap-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
          <span>Card numbers, CVV & OTPs automatically masked</span>
        </div>
      </div>

      {/* Terminal View Container */}
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl p-4 shadow-xl font-mono text-xs overflow-x-auto h-[600px] flex flex-col">
        <div className="flex-1 overflow-y-auto space-y-1.5 pr-2">
          {logs.length > 0 ? (
            logs.map((l) => (
              <div key={l.id} className="flex items-start gap-3 py-1 hover:bg-zinc-900/60 px-2 rounded-md">
                <span className="text-zinc-500 text-[11px] shrink-0">{l.timestamp}</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0 border ${levelColor(l.level)}`}>
                  {l.level}
                </span>
                <span className="text-zinc-400 text-[11px] shrink-0">[{l.category}]</span>
                {l.booking_ref && (
                  <span className="text-sky-400 text-[11px] shrink-0 font-bold">{l.booking_ref}:</span>
                )}
                <span className="text-zinc-200 break-all">{l.message}</span>
              </div>
            ))
          ) : (
            <div className="h-full flex items-center justify-center text-zinc-600">
              No logs recorded matching current criteria.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
