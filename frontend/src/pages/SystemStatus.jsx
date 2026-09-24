import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Server, 
  Database, 
  Monitor, 
  Send, 
  MessageSquare, 
  FileSpreadsheet, 
  CheckCircle2, 
  XCircle, 
  RefreshCw,
  HardDriveDownload
} from 'lucide-react';
import { fetchSystemStatus, triggerBackup } from '../services/api';

export default function SystemStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [backupMsg, setBackupMsg] = useState(null);
  const [backingUp, setBackingUp] = useState(false);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const data = await fetchSystemStatus();
      setStatus(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleBackup = async () => {
    setBackingUp(true);
    setBackupMsg(null);
    try {
      const res = await triggerBackup();
      setBackupMsg(`Database backup snapshot saved to: ${res.backup_path}`);
    } catch (err) {
      setBackupMsg(`Backup failed: ${err.message}`);
    } finally {
      setBackingUp(false);
    }
  };

  const isHealthy = (val) => val === 'Online' || val === 'Connected' || val === 'Ready';

  const components = [
    { name: 'FastAPI Backend Engine', status: status?.backend || 'Offline', icon: Server, desc: 'Local REST and automation worker' },
    { name: 'SQLite Database', status: status?.database || 'Disconnected', icon: Database, desc: 'Local persistent storage and CRM tables' },
    { name: 'Playwright Browser Session', status: status?.browser_automation || 'Ready', icon: Monitor, desc: 'Visible Chromium automation pool' },
    { name: 'Telegram Bot Gateway', status: status?.telegram || 'Disconnected', icon: Send, desc: 'Instant push notifications' },
    { name: 'WhatsApp Cloud API', status: status?.whatsapp || 'Disconnected', icon: MessageSquare, desc: 'Official Meta WhatsApp Business provider' },
    { name: 'Excel Master Sheet (openpyxl)', status: status?.excel || 'Error', icon: FileSpreadsheet, desc: 'Auto-appending bookings.xlsx engine' },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">System Status & Connectivity</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Real-time diagnostics for automation subsystems, database, and notification pipelines
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleBackup}
            disabled={backingUp}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-xs flex items-center gap-2 cursor-pointer disabled:opacity-50"
          >
            <HardDriveDownload className="w-4 h-4" />
            {backingUp ? 'Backing up...' : 'Backup Database Now'}
          </button>

          <button
            onClick={loadStatus}
            className="p-2 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-xl text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {backupMsg && (
        <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs text-emerald-700 dark:text-emerald-300">
          {backupMsg}
        </div>
      )}

      {/* Grid of status cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {components.map((c) => {
          const Icon = c.icon;
          const healthy = isHealthy(c.status);
          return (
            <div
              key={c.name}
              className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-xs flex items-center justify-between"
            >
              <div className="flex items-center gap-3.5">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  healthy 
                    ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-600 dark:text-emerald-400' 
                    : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400'
                }`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="font-bold text-xs text-zinc-900 dark:text-white">{c.name}</h4>
                  <p className="text-[11px] text-zinc-400 mt-0.5">{c.desc}</p>
                </div>
              </div>

              <div>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                  healthy
                    ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                    : 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20'
                }`}>
                  {healthy ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                  {c.status}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Environment parameters */}
      <div className="bg-zinc-50 dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 text-xs space-y-2">
        <h4 className="font-bold text-zinc-900 dark:text-white">Active Operating Parameters</h4>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 text-zinc-600 dark:text-zinc-400">
          <div>
            <span className="text-[10px] text-zinc-400 uppercase">MODE</span>
            <p className="font-semibold text-emerald-600 dark:text-emerald-400">Live Official IRCTC Mode</p>
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 uppercase">ENVIRONMENT</span>
            <p className="font-semibold text-zinc-900 dark:text-white">{status?.app_env || 'development'}</p>
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 uppercase">SECURITY STATUS</span>
            <p className="font-semibold text-emerald-600 dark:text-emerald-400">Zero Bypass Compliant</p>
          </div>
          <div>
            <span className="text-[10px] text-zinc-400 uppercase">TARGET MACHINE</span>
            <p className="font-semibold text-zinc-900 dark:text-white">Low-Spec (4–8 GB RAM)</p>
          </div>
        </div>
      </div>
    </div>
  );
}
