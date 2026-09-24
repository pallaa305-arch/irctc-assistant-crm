import React from 'react';
import { 
  LayoutDashboard, 
  Sparkles,
  Ticket, 
  History, 
  Users, 
  UserCheck, 
  MapPin, 
  Bell, 
  Settings, 
  Terminal, 
  Activity,
  Train,
  Radio
} from 'lucide-react';

export default function Sidebar({ currentTab, setTab, isOpen, setIsOpen }) {
  const navigation = [
    { id: 'dashboard', name: 'Dashboard', icon: LayoutDashboard },
    { id: 'ai-assistant', name: 'AI Assistant', icon: Sparkles, highlight: true },
    { id: 'new-booking', name: 'New Booking', icon: Ticket },
    { id: 'pnr-live-tracking', name: 'PNR & Live Train', icon: Radio },
    { id: 'booking-history', name: 'Booking History', icon: History },
    { id: 'crm', name: 'CRM', icon: Users },
    { id: 'passengers', name: 'Passengers', icon: UserCheck },
    { id: 'saved-journeys', name: 'Saved Journeys', icon: MapPin },
    { id: 'notifications', name: 'Notifications', icon: Bell },
    { id: 'settings', name: 'Settings', icon: Settings },
    { id: 'logs', name: 'Logs', icon: Terminal },
    { id: 'system-status', name: 'System Status', icon: Activity },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div 
          onClick={() => setIsOpen(false)}
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
        />
      )}

      <aside className={`fixed top-0 bottom-0 left-0 z-40 w-64 glass-panel border-r border-black/5 dark:border-white/10 transition-transform duration-200 flex flex-col ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        {/* Brand header */}
        <div className="h-16 border-b border-black/5 dark:border-white/10 px-6 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center text-white shadow-md shadow-emerald-600/30">
            <Train className="w-5 h-5" />
          </div>
          <div>
            <h1 className="font-bold text-sm tracking-tight text-zinc-900 dark:text-white">IRCTC Assistant</h1>
            <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">Personal CRM & Automation</p>
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {navigation.map((item) => {
            const Icon = item.icon;
            const active = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setTab(item.id);
                  setIsOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-semibold transition-all cursor-pointer ${
                  active 
                    ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/25' 
                    : item.highlight
                    ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-50/50 dark:bg-emerald-950/20 hover:bg-emerald-100/60 dark:hover:bg-emerald-900/40'
                    : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-900'
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? 'text-white' : item.highlight ? 'text-emerald-500' : 'text-zinc-400'}`} />
                <span>{item.name}</span>
                {item.highlight && !active && (
                  <span className="ml-auto w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Safety & Compliance Badge */}
        <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/50 m-3 rounded-xl text-[11px] text-zinc-500 dark:text-zinc-400">
          <p className="font-semibold text-zinc-700 dark:text-zinc-200">🛡️ Compliant Assistant</p>
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-0.5">Human-in-the-loop. Zero CAPTCHA/OTP bypass.</p>
        </div>
      </aside>
    </>
  );
}
