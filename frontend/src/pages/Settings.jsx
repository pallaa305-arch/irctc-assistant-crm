import React, { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, 
  Monitor, 
  Cpu, 
  ShieldAlert, 
  Trash2, 
  Save, 
  CheckCircle2, 
  AlertTriangle,
  Lock
} from 'lucide-react';
import { fetchSettings, updateSettings, deleteAllData } from '../services/api';

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [irctcUser, setIrctcUser] = useState('');
  const [irctcPassword, setIrctcPassword] = useState('');
  const [demoMode, setDemoMode] = useState(false);
  const [browserHeadless, setBrowserHeadless] = useState(false);
  const [slowMo, setSlowMo] = useState(150);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [wipingData, setWipingData] = useState(false);

  useEffect(() => {
    fetchSettings().then((d) => {
      setSettings(d);
      setIrctcUser(d.irctc_username || '');
      setIrctcPassword(d.irctc_password_masked || '');
      setDemoMode(d.demo_mode ?? false);
      setBrowserHeadless(d.browser_headless ?? false);
      setSlowMo(d.browser_slow_mo ?? 150);
    });
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    try {
      await updateSettings({
        irctc_username: irctcUser,
        irctc_password: irctcPassword,
        demo_mode: demoMode,
        browser_headless: browserHeadless,
        browser_slow_mo: parseInt(slowMo) || 150,
      });
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      alert('Error updating settings: ' + err.message);
    }
  };

  const handleDeleteAll = async () => {
    const confirmation = prompt('DANGER ZONE: Type "DELETE" to permanently erase all personal bookings, passengers, and logs:');
    if (confirmation !== 'DELETE') return;

    setWipingData(true);
    try {
      await deleteAllData();
      alert('All local database records and Excel files have been purged.');
      window.location.reload();
    } catch (err) {
      alert('Error wiping data: ' + err.message);
    } finally {
      setWipingData(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in pb-12">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">System Settings & Preferences</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
          Browser automation behavior, account references, and privacy purge
        </p>
      </div>

      {savedSuccess && (
        <div className="p-4 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl flex items-center gap-3 text-xs text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 className="w-5 h-5" />
          <span>Configuration saved successfully!</span>
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6 text-xs">
        {/* IRCTC & Automation Behavior */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-100 dark:border-zinc-800 pb-3">
            <Monitor className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h3 className="font-bold text-sm text-zinc-900 dark:text-white">IRCTC Account & Browser Automation</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                IRCTC Username (User ID)
              </label>
              <input
                type="text"
                value={irctcUser}
                onChange={(e) => setIrctcUser(e.target.value)}
                placeholder="IRCTC User ID"
                className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              />
              <p className="text-[10px] text-zinc-400 mt-1">Saved in local .env for login auto-fill.</p>
            </div>

            <div>
              <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                IRCTC Password (Saved safely in .env)
              </label>
              <input
                type="password"
                value={irctcPassword}
                onChange={(e) => setIrctcPassword(e.target.value)}
                placeholder="IRCTC Account Password"
                className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              />
              <p className="text-[10px] text-zinc-400 mt-1">Auto-fills password during IRCTC login.</p>
            </div>

            <div>
              <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
                SlowMo Delay (Milliseconds)
              </label>
              <input
                type="number"
                min="0"
                max="1000"
                step="50"
                value={slowMo}
                onChange={(e) => setSlowMo(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              />
              <p className="text-[10px] text-zinc-400 mt-1">Human-pace slowdown so you can inspect browser movements visually.</p>
            </div>
          </div>

          <div className="pt-2 space-y-3">
            <label className="flex items-center gap-3 cursor-pointer p-3 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl border border-zinc-200/60 dark:border-zinc-800">
              <input
                type="checkbox"
                checked={!browserHeadless}
                onChange={(e) => setBrowserHeadless(!e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500"
              />
              <div>
                <span className="font-bold text-zinc-900 dark:text-white">Visible Browser Mode (Recommended)</span>
                <p className="text-[11px] text-zinc-400">
                  Launches a real Chromium window so you can watch progress and seamlessly enter CAPTCHA/OTP.
                </p>
              </div>
            </label>

            <label className="flex items-center gap-3 cursor-pointer p-3 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl border border-zinc-200/60 dark:border-zinc-800">
              <input
                type="checkbox"
                checked={demoMode}
                onChange={(e) => setDemoMode(e.target.checked)}
                className="rounded text-emerald-600 focus:ring-emerald-500"
              />
              <div>
                <span className="font-bold text-zinc-900 dark:text-white">Default to Demo Mode</span>
                <p className="text-[11px] text-zinc-400">
                  Safe test runs without real financial charges or IRCTC website traffic.
                </p>
              </div>
            </label>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              className="px-5 py-2 font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs cursor-pointer flex items-center gap-1.5"
            >
              <Save className="w-4 h-4" /> Save Settings
            </button>
          </div>
        </div>
      </form>

      {/* Low Spec Optimization Info */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs space-y-3 text-xs">
        <div className="flex items-center gap-2 text-zinc-900 dark:text-white font-bold">
          <Cpu className="w-4 h-4 text-emerald-600" /> Low-Spec Hardware Optimization Details
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
          This system is strictly architected for 4–8 GB RAM machines. It runs on a single Python process, uses zero GPU resources, requires no heavy local AI models or Ollama, and pools a single browser instance that closes automatically after inactivity.
        </p>
      </div>

      {/* Privacy & Danger Zone */}
      <div className="bg-rose-50/50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900/50 rounded-2xl p-6 shadow-xs space-y-3 text-xs">
        <div className="flex items-center gap-2 text-rose-700 dark:text-rose-400 font-bold">
          <Trash2 className="w-4 h-4" /> Privacy Control: Wipe All Local Data
        </div>
        <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed">
          In accordance with personal privacy requirements (Section 32), you can permanently delete all booking records, passenger profiles, logs, and Excel history from this machine with a single click.
        </p>
        <button
          onClick={handleDeleteAll}
          disabled={wipingData}
          className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-xl transition-colors cursor-pointer disabled:opacity-50"
        >
          {wipingData ? 'Erasing Everything...' : 'Permanently Delete All Data'}
        </button>
      </div>
    </div>
  );
}
