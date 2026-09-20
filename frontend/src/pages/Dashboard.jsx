import React, { useState, useEffect } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  IndianRupee, 
  Calendar, 
  ArrowRight, 
  Train, 
  TrendingUp,
  RefreshCw,
  PlusCircle,
  Radio,
  Search
} from 'lucide-react';
import { fetchStats } from '../services/api';
import StatusBadge from '../components/StatusBadge';

export default function Dashboard({ setTab, onSelectBookingForTracking }) {
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  const loadStats = async () => {
    setLoading(true);
    try {
      const data = await fetchStats(filter === 'all' ? null : filter);
      setStats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
  }, [filter]);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header & Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Booking Dashboard</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Real-time railway booking analytics and upcoming journeys
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Time range filters */}
          <div className="bg-zinc-100 dark:bg-zinc-900 p-1 rounded-xl flex items-center gap-1 border border-zinc-200 dark:border-zinc-800 text-xs">
            {[
              { id: 'all', label: 'All Time' },
              { id: 'today', label: 'Today' },
              { id: 'this_week', label: 'This Week' },
              { id: 'this_month', label: 'This Month' },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setFilter(t.id)}
                className={`px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer ${
                  filter === t.id
                    ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white shadow-xs'
                    : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-white'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <button
            onClick={loadStats}
            className="p-2 bg-zinc-100 dark:bg-zinc-900 hover:bg-zinc-200 dark:hover:bg-zinc-800 rounded-xl border border-zinc-200 dark:border-zinc-800 text-zinc-600 dark:text-zinc-300 transition-colors cursor-pointer"
            title="Refresh statistics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setTab('new-booking')}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-2 cursor-pointer transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            New Booking
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-4 rounded-2xl shadow-xs">
          <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Total Bookings</p>
          <p className="text-2xl font-bold text-zinc-900 dark:text-white mt-2">
            {stats?.total_bookings ?? 0}
          </p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-zinc-400">
            <Train className="w-3 h-3" />
            <span>All sessions</span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-4 rounded-2xl shadow-xs">
          <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Confirmed</p>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-2">
            {stats?.successful_bookings ?? 0}
          </p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-emerald-600/80">
            <CheckCircle2 className="w-3 h-3" />
            <span>Success rate</span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-4 rounded-2xl shadow-xs">
          <p className="text-xs text-amber-600 dark:text-amber-400 font-medium">Pending / Active</p>
          <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 mt-2">
            {stats?.pending_bookings ?? 0}
          </p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-amber-600/80">
            <Clock className="w-3 h-3" />
            <span>In flight</span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-4 rounded-2xl shadow-xs">
          <p className="text-xs text-rose-600 dark:text-rose-400 font-medium">Failed</p>
          <p className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-2">
            {stats?.failed_bookings ?? 0}
          </p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-rose-600/80">
            <XCircle className="w-3 h-3" />
            <span>Unfinished</span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-4 rounded-2xl shadow-xs">
          <p className="text-xs text-sky-600 dark:text-sky-400 font-medium">Upcoming</p>
          <p className="text-2xl font-bold text-sky-600 dark:text-sky-400 mt-2">
            {stats?.upcoming_count ?? 0}
          </p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-sky-600/80">
            <Calendar className="w-3 h-3" />
            <span>Journeys ahead</span>
          </div>
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-4 rounded-2xl shadow-xs">
          <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Total Spend (Rs.)</p>
          <p className="text-2xl font-bold text-zinc-900 dark:text-white mt-2">
            Rs. {stats?.total_spend ? stats.total_spend.toLocaleString('en-IN') : '0'}
          </p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-zinc-400">
            <IndianRupee className="w-3 h-3" />
            <span>Confirmed fare</span>
          </div>
        </div>
      </div>

      {/* Quick Live Enquiry Banner */}
      <div className="bg-gradient-to-r from-emerald-800 via-teal-800 to-indigo-900 rounded-2xl p-5 text-white shadow-lg flex flex-col md:flex-row items-center justify-between gap-4 border border-emerald-700/30">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center backdrop-blur-md shrink-0">
            <Radio className="w-6 h-6 text-emerald-300 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase font-bold tracking-wider bg-emerald-500/30 text-emerald-200 px-2.5 py-0.5 rounded-full">
                Live Indian Railways Enquiry
              </span>
              <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded-full font-mono">
                100% Real-Time
              </span>
            </div>
            <h3 className="text-base font-bold text-white mt-1">
              Check 10-Digit PNR Status & Live Train Running Status
            </h3>
            <p className="text-xs text-emerald-100/80 mt-0.5">
              Instant coach & berth verification, live delay tracking, upcoming station ETA, and express route finder.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 w-full md:w-auto shrink-0">
          <button
            onClick={() => setTab('pnr-live-tracking')}
            className="flex-1 md:flex-none px-4 py-2.5 bg-white text-zinc-900 hover:bg-emerald-50 text-xs font-bold rounded-xl shadow-sm transition-colors flex items-center justify-center gap-2 cursor-pointer"
          >
            <Search className="w-3.5 h-3.5 text-emerald-600" />
            Check PNR Status
          </button>
          <button
            onClick={() => setTab('pnr-live-tracking')}
            className="flex-1 md:flex-none px-4 py-2.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-white/20 text-white text-xs font-semibold rounded-xl transition-colors flex items-center justify-center gap-2 cursor-pointer"
          >
            <Train className="w-3.5 h-3.5" />
            Track Live Train
          </button>
        </div>
      </div>

      {/* Two-Column Section: Upcoming Journeys & Recent Bookings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Upcoming Journeys Card */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">Upcoming Journeys</h3>
            </div>
            <button
              onClick={() => setTab('booking-history')}
              className="text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 flex items-center gap-1 cursor-pointer font-medium"
            >
              View all <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="flex-1 space-y-3">
            {stats?.upcoming_journeys && stats.upcoming_journeys.length > 0 ? (
              stats.upcoming_journeys.map((j) => (
                <div
                  key={j.id}
                  className="p-3 bg-zinc-50 dark:bg-zinc-800/50 rounded-xl border border-zinc-200/80 dark:border-zinc-800 flex items-center justify-between"
                >
                  <div>
                    <p className="text-xs font-bold text-zinc-900 dark:text-white">{j.route}</p>
                    <p className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">{j.train} • {j.journey_date}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">PNR: {j.pnr || 'TBD'}</span>
                    <p className="text-[10px] text-zinc-400 mt-0.5">{j.passengers} Passenger(s)</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="h-40 flex flex-col items-center justify-center text-zinc-400 text-xs text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
                <Train className="w-8 h-8 mb-2 opacity-30" />
                <p>No upcoming journeys scheduled.</p>
                <button
                  onClick={() => setTab('new-booking')}
                  className="mt-2 text-emerald-600 font-semibold cursor-pointer"
                >
                  Plan a new journey →
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Recent Bookings Activity */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-xs flex flex-col">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">Recent Activity</h3>
            </div>
            <button
              onClick={() => setTab('crm')}
              className="text-xs text-emerald-600 hover:text-emerald-700 dark:text-emerald-400 flex items-center gap-1 cursor-pointer font-medium"
            >
              CRM records <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="flex-1 space-y-3">
            {stats?.recent_bookings && stats.recent_bookings.length > 0 ? (
              stats.recent_bookings.map((b) => (
                <div
                  key={b.id}
                  onClick={() => onSelectBookingForTracking(b.booking_ref)}
                  className="p-3 bg-zinc-50 dark:bg-zinc-800/50 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-xl border border-zinc-200/80 dark:border-zinc-800 flex items-center justify-between cursor-pointer transition-colors"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-zinc-900 dark:text-white">{b.route}</span>
                      <StatusBadge status={b.status} />
                    </div>
                    <p className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                      Ref: {b.booking_ref} • {b.created_at}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-bold text-zinc-900 dark:text-white">Rs. {b.fare || 0}</p>
                    <p className="text-[10px] text-zinc-400 font-mono mt-0.5">{b.pnr ? `PNR: ${b.pnr}` : 'Pending'}</p>
                  </div>
                </div>
              ))
            ) : (
              <div className="h-40 flex flex-col items-center justify-center text-zinc-400 text-xs text-center border border-dashed border-zinc-200 dark:border-zinc-800 rounded-xl">
                <p>No recent booking activity found.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
