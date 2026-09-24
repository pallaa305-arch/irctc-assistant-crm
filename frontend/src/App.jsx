import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import ManualActionModal from './components/ManualActionModal';
import StatusBadge from './components/StatusBadge';

// Import 10 Views
import Dashboard from './pages/Dashboard';
import NewBooking from './pages/NewBooking';
import BookingHistory from './pages/BookingHistory';
import CRMView from './pages/CRMView';
import Passengers from './pages/Passengers';
import SavedJourneys from './pages/SavedJourneys';
import Notifications from './pages/Notifications';
import Settings from './pages/Settings';
import Logs from './pages/Logs';
import SystemStatus from './pages/SystemStatus';
import PNRLiveTracking from './pages/PNRLiveTracking';
import AIAssistant from './pages/AIAssistant';

import { getBookingState, sendBookingAction, fetchBookings } from './services/api';
import { ShieldCheck, AlertTriangle, ArrowRight, CheckCircle2, Clock } from 'lucide-react';

export default function App() {
  const [currentTab, setTab] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('irctc_theme');
    if (saved) return saved === 'dark';
    return true; // Modern dark glass theme by default
  });

  // Active booking tracking
  const [activeBookingRef, setActiveBookingRef] = useState(null);
  const [activeBookingState, setActiveBookingState] = useState(null);

  // Apply dark mode class to root HTML element and persist
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('irctc_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('irctc_theme', 'light');
    }
  }, [darkMode]);

  // Auto-discover any active booking triggered externally (e.g. from Telegram)
  useEffect(() => {
    let isSubscribed = true;
    const checkActiveBookings = async () => {
      try {
        if (!activeBookingRef || (activeBookingState && ['CONFIRMED', 'FAILED', 'CANCELLED'].includes(activeBookingState.status))) {
          const res = await fetchBookings({ limit: 5 });
          if (isSubscribed && res && res.items) {
            const active = res.items.find(b =>
              ['WAITING_MANUAL', 'PAYMENT_PENDING', 'IN_PROGRESS', 'INITIATED'].includes(b.status)
            );
            if (active && active.booking_ref !== activeBookingRef) {
              setActiveBookingRef(active.booking_ref);
            }
          }
        }
      } catch (err) {
        // silent polling catch
      }
    };

    checkActiveBookings();
    const interval = setInterval(checkActiveBookings, 8000);
    return () => {
      isSubscribed = false;
      clearInterval(interval);
    };
  }, [activeBookingRef, activeBookingState?.status]);

  // Poller for active booking state machine with adaptive interval & terminal auto-stop
  useEffect(() => {
    if (!activeBookingRef) return;

    let isSubscribed = true;
    let timerId = null;

    const poll = async () => {
      try {
        const state = await getBookingState(activeBookingRef);
        if (isSubscribed) {
          setActiveBookingState(state);
          // Auto-stop polling if reached terminal state
          const terminal = ['CONFIRMED', 'FAILED', 'CANCELLED'];
          if (terminal.includes(state.status)) {
            return; // Terminate polling
          }
          // Adaptive interval: slower for waiting states, faster for active
          const waitingStates = ['WAITING_MANUAL', 'PAYMENT_PENDING'];
          const interval = waitingStates.includes(state.status) ? 5000 : 2000;
          timerId = setTimeout(poll, interval);
        }
      } catch (err) {
        console.error('Error polling booking state:', err);
        if (isSubscribed) {
          setActiveBookingRef(null);
        }
      }
    };

    poll();
    return () => {
      isSubscribed = false;
      if (timerId) clearTimeout(timerId);
    };
  }, [activeBookingRef]);

  const handleBookingStarted = (bookingRef) => {
    setActiveBookingRef(bookingRef);
    setTab('dashboard');
  };

  const handleSelectBookingForTracking = (bookingRef) => {
    setActiveBookingRef(bookingRef);
  };

  const handleUserAction = async (action, inputValue = null) => {
    if (!activeBookingRef) return;
    try {
      await sendBookingAction(activeBookingRef, action, null, inputValue);
      // Immediately refresh state
      const updated = await getBookingState(activeBookingRef);
      setActiveBookingState(updated);
    } catch (err) {
      alert('Action error: ' + err.message);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50/90 dark:bg-[#090b10] text-zinc-900 dark:text-zinc-100 flex flex-col antialiased transition-colors relative selection:bg-emerald-500 selection:text-white">
      {/* Ambient background glow for glass theme */}
      <div className="fixed top-[-10%] left-[-10%] w-[45vw] h-[45vw] rounded-full bg-emerald-500/10 dark:bg-emerald-500/5 blur-[120px] pointer-events-none -z-10" />
      <div className="fixed bottom-[-10%] right-[-10%] w-[50vw] h-[50vw] rounded-full bg-teal-500/10 dark:bg-cyan-500/5 blur-[140px] pointer-events-none -z-10" />

      {/* Sidebar Navigation */}
      <Sidebar
        currentTab={currentTab}
        setTab={setTab}
        isOpen={sidebarOpen}
        setIsOpen={setSidebarOpen}
      />

      {/* Main Content Area */}
      <div className="lg:pl-64 flex-1 flex flex-col">
        <Navbar
          onMenuToggle={() => setSidebarOpen(!sidebarOpen)}
          darkMode={darkMode}
          setDarkMode={setDarkMode}
          activeBookingState={activeBookingState}
        />

        {/* Global Active Automation Notification / Stage Tracker */}
        {activeBookingState && (
          <div className="bg-emerald-600 dark:bg-emerald-800 text-white px-4 lg:px-8 py-2.5 flex flex-wrap items-center justify-between gap-3 text-xs shadow-md">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-white animate-ping"></span>
              <span className="font-bold">Active Booking:</span>
              <span className="font-mono bg-white/20 px-2 py-0.5 rounded">{activeBookingState.booking_ref}</span>
              <span>({activeBookingState.from_station} ➔ {activeBookingState.to_station})</span>
            </div>

            <div className="flex items-center gap-3">
              <span className="bg-emerald-950/40 px-2.5 py-1 rounded-md font-semibold flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" /> Stage: {activeBookingState.stage}
              </span>
              <StatusBadge status={activeBookingState.status} />
              {activeBookingState.pnr && (
                <span className="bg-white text-emerald-900 font-bold px-2 py-0.5 rounded">
                  PNR: {activeBookingState.pnr}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Dynamic Page Views */}
        <main className="flex-1 p-4 lg:p-8 max-w-7xl w-full mx-auto">
          {currentTab === 'dashboard' && (
            <Dashboard
              setTab={setTab}
              onSelectBookingForTracking={handleSelectBookingForTracking}
            />
          )}
          {currentTab === 'ai-assistant' && (
            <AIAssistant setTab={setTab} />
          )}
          {currentTab === 'new-booking' && (
            <NewBooking onBookingStarted={handleBookingStarted} />
          )}
          {currentTab === 'booking-history' && (
            <BookingHistory
              onSelectBookingForTracking={handleSelectBookingForTracking}
            />
          )}
          {currentTab === 'crm' && <CRMView />}
          {currentTab === 'passengers' && <Passengers />}
          {currentTab === 'saved-journeys' && <SavedJourneys setTab={setTab} />}
          {currentTab === 'pnr-live-tracking' && <PNRLiveTracking setTab={setTab} />}
          {currentTab === 'notifications' && <Notifications />}
          {currentTab === 'settings' && <Settings />}
          {currentTab === 'logs' && <Logs />}
          {currentTab === 'system-status' && <SystemStatus />}
        </main>
      </div>

      {/* Human-in-the-Loop Verification & Payment Handover Modal */}
      <ManualActionModal
        state={activeBookingState}
        onAction={handleUserAction}
      />
    </div>
  );
}
