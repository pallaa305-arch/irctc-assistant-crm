import React, { useState, useEffect } from 'react';
import { 
  Send, 
  MessageSquare, 
  Bell, 
  CheckCircle2, 
  AlertCircle, 
  Radio, 
  ExternalLink,
  ShieldCheck,
  Check
} from 'lucide-react';
import { fetchSettings, updateSettings, testTelegram, testWhatsApp } from '../services/api';

export default function Notifications() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testingTg, setTestingTg] = useState(false);
  const [testingWa, setTestingWa] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  // Form states
  const [tgToken, setTgToken] = useState('');
  const [tgChatId, setTgChatId] = useState('');
  const [tgEnabled, setTgEnabled] = useState(false);

  const [waApiKey, setWaApiKey] = useState('');
  const [waPhoneId, setWaPhoneId] = useState('');
  const [waRecipient, setWaRecipient] = useState('');
  const [waEnabled, setWaEnabled] = useState(false);

  useEffect(() => {
    fetchSettings().then((data) => {
      setSettings(data);
      setTgChatId(data.telegram_chat_id || '');
      setTgEnabled(data.telegram_enabled || false);
      setWaPhoneId(data.whatsapp_phone_number_id || '');
      setWaRecipient(data.whatsapp_recipient_phone || '');
      setWaEnabled(data.whatsapp_enabled || false);
      setLoading(false);
    });
  }, []);

  const handleSaveTelegram = async () => {
    try {
      const payload = {
        telegram_chat_id: tgChatId,
        telegram_enabled: tgEnabled,
      };
      if (tgToken.trim()) {
        payload.telegram_bot_token = tgToken.trim();
      }
      await updateSettings(payload);
      setStatusMsg({ type: 'success', text: 'Telegram settings saved.' });
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    }
  };

  const handleTestTelegram = async () => {
    setTestingTg(true);
    setStatusMsg(null);
    try {
      // Auto-save current form values first so backend has latest token & chat ID
      const payload = {
        telegram_chat_id: tgChatId,
        telegram_enabled: tgEnabled,
      };
      if (tgToken.trim()) {
        payload.telegram_bot_token = tgToken.trim();
      }
      await updateSettings(payload);

      const res = await testTelegram();
      setStatusMsg({ type: 'success', text: res.message });
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setTestingTg(false);
    }
  };

  const handleSaveWhatsApp = async () => {
    try {
      const payload = {
        whatsapp_phone_number_id: waPhoneId,
        whatsapp_recipient_phone: waRecipient,
        whatsapp_enabled: waEnabled,
      };
      if (waApiKey.trim()) {
        payload.whatsapp_api_key = waApiKey.trim();
      }
      await updateSettings(payload);
      setStatusMsg({ type: 'success', text: 'WhatsApp configuration saved.' });
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    }
  };

  const handleTestWhatsApp = async () => {
    setTestingWa(true);
    setStatusMsg(null);
    try {
      const res = await testWhatsApp();
      setStatusMsg({ type: 'success', text: res.message });
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.message });
    } finally {
      setTestingWa(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in pb-12">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Notification Integrations</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
          Receive real-time alerts when security handoff or booking confirmations occur.
        </p>
      </div>

      {statusMsg && (
        <div className={`p-4 rounded-xl flex items-center gap-3 text-xs border ${
          statusMsg.type === 'success' 
            ? 'bg-emerald-50 dark:bg-emerald-950/40 border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300' 
            : 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300'
        }`}>
          {statusMsg.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <span>{statusMsg.text}</span>
        </div>
      )}

      {/* Telegram Card */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <Send className="w-5 h-5 text-sky-500" />
            <div>
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">Telegram Bot Notifications</h3>
              <p className="text-[11px] text-zinc-400">Direct instant push messages for PNR confirmations and manual actions</p>
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={tgEnabled}
              onChange={(e) => setTgEnabled(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-zinc-200 peer-focus:outline-hidden rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-zinc-600 peer-checked:bg-emerald-600"></div>
          </label>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              Bot Token (from @BotFather)
            </label>
            <input
              type="password"
              value={tgToken}
              onChange={(e) => setTgToken(e.target.value)}
              placeholder={settings?.telegram_bot_token_masked || "Enter Bot Token"}
              className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500 font-mono"
            />
          </div>

          <div>
            <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              Target Chat ID
            </label>
            <input
              type="text"
              value={tgChatId}
              onChange={(e) => setTgChatId(e.target.value)}
              placeholder="e.g. 123456789"
              className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500 font-mono"
            />
          </div>
        </div>

        <div className="p-3 bg-sky-50 dark:bg-sky-950/30 border border-sky-200 dark:border-sky-800 rounded-xl text-[11px] text-sky-800 dark:text-sky-300">
          💡 <strong>Zaroori Step:</strong> Bot banane ke baad Telegram me apne bot ko search karke <strong>/start</strong> zaroor bhejein, warna Telegram bot ko pehla message bhejne se block kar deta hai.
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleTestTelegram}
            disabled={testingTg}
            className="px-4 py-2 text-xs font-semibold text-zinc-700 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-xl transition-colors cursor-pointer disabled:opacity-50"
          >
            {testingTg ? 'Testing...' : 'Send Test Alert'}
          </button>
          <button
            type="button"
            onClick={handleSaveTelegram}
            className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs cursor-pointer flex items-center gap-1.5"
          >
            <Check className="w-4 h-4" /> Save Telegram Settings
          </button>
        </div>
      </div>

      {/* WhatsApp Official Cloud API Card */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-emerald-500" />
            <div>
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">Authorized WhatsApp Cloud API</h3>
              <p className="text-[11px] text-zinc-400">Uses official Meta / WhatsApp Cloud API endpoints. Zero web scraping.</p>
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={waEnabled}
              onChange={(e) => setWaEnabled(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-9 h-5 bg-zinc-200 peer-focus:outline-hidden rounded-full peer dark:bg-zinc-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all dark:border-zinc-600 peer-checked:bg-emerald-600"></div>
          </label>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              WhatsApp Access Token / API Key
            </label>
            <input
              type="password"
              value={waApiKey}
              onChange={(e) => setWaApiKey(e.target.value)}
              placeholder="Bearer Token"
              className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500 font-mono"
            />
          </div>

          <div>
            <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              Phone Number ID
            </label>
            <input
              type="text"
              value={waPhoneId}
              onChange={(e) => setWaPhoneId(e.target.value)}
              placeholder="e.g. 10485938592"
              className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500 font-mono"
            />
          </div>

          <div>
            <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">
              Recipient Phone (with country code)
            </label>
            <input
              type="text"
              value={waRecipient}
              onChange={(e) => setWaRecipient(e.target.value)}
              placeholder="e.g. 919876543210"
              className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500 font-mono"
            />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={handleTestWhatsApp}
            disabled={testingWa}
            className="px-4 py-2 text-xs font-semibold text-zinc-700 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-xl transition-colors cursor-pointer disabled:opacity-50"
          >
            {testingWa ? 'Testing...' : 'Send Test Alert'}
          </button>
          <button
            type="button"
            onClick={handleSaveWhatsApp}
            className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-xs cursor-pointer flex items-center gap-1.5"
          >
            <Check className="w-4 h-4" /> Save WhatsApp Settings
          </button>
        </div>
      </div>

      {/* Events Coverage Checklist */}
      <div className="bg-zinc-50 dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 text-xs space-y-3">
        <h4 className="font-bold text-zinc-800 dark:text-zinc-200 flex items-center gap-2">
          <Bell className="w-4 h-4 text-emerald-600" /> Supported Notification Lifecycle Events
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 text-zinc-600 dark:text-zinc-400">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Booking Started
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Train Found & Selected
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500"></span> Manual CAPTCHA Required
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500"></span> Manual OTP Required
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500"></span> Payment Gateway Handoff
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Booking Confirmed (with PNR)
          </div>
        </div>
      </div>
    </div>
  );
}
