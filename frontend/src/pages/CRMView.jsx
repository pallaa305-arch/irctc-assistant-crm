import React, { useState, useEffect } from 'react';
import { 
  Users, 
  IndianRupee, 
  Send, 
  MessageSquare, 
  Train, 
  Calendar, 
  FileText, 
  Search,
  CheckCircle,
  AlertTriangle,
  Clock
} from 'lucide-react';
import { fetchBookings } from '../services/api';
import StatusBadge from '../components/StatusBadge';

export default function CRMView() {
  const [bookings, setBookings] = useState([]);
  const [selectedBooking, setSelectedBooking] = useState(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    fetchBookings({ limit: 100 }).then((res) => {
      setBookings(res.items);
      if (res.items.length > 0) {
        setSelectedBooking(res.items[0]);
      }
    });
  }, []);

  const filtered = bookings.filter((b) => 
    b.booking_ref.toLowerCase().includes(search.toLowerCase()) ||
    (b.pnr && b.pnr.includes(search)) ||
    b.from_station.toLowerCase().includes(search.toLowerCase()) ||
    b.to_station.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">CRM & Journey Relations</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
          Detailed passenger assignments, notification delivery logs, and journey records
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Master List of Bookings */}
        <div className="lg:col-span-5 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-xs flex flex-col h-[650px]">
          <div className="relative mb-3">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by ref, PNR, station..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
            />
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {filtered.map((b) => {
              const active = selectedBooking?.id === b.id;
              return (
                <div
                  key={b.id}
                  onClick={() => setSelectedBooking(b)}
                  className={`p-3 rounded-xl border transition-all cursor-pointer ${
                    active
                      ? 'bg-emerald-50 dark:bg-emerald-950/30 border-emerald-500/50 shadow-xs'
                      : 'bg-zinc-50 dark:bg-zinc-800/40 border-zinc-200/80 dark:border-zinc-800 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-zinc-900 dark:text-white">
                      {b.booking_ref}
                    </span>
                    <StatusBadge status={b.status} />
                  </div>
                  <p className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 mt-1">
                    {b.from_station} ➔ {b.to_station}
                  </p>
                  <div className="flex items-center justify-between text-[11px] text-zinc-400 mt-1">
                    <span>{b.journey_date}</span>
                    <span className="font-mono">{b.pnr ? `PNR: ${b.pnr}` : 'No PNR'}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Detailed CRM Record Dossier */}
        <div className="lg:col-span-7 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs h-[650px] overflow-y-auto">
          {selectedBooking ? (
            <div className="space-y-6">
              {/* Top Banner */}
              <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-4">
                <div>
                  <span className="text-[11px] font-mono text-zinc-400">BOOKING RECORD</span>
                  <h3 className="text-lg font-bold text-zinc-900 dark:text-white">{selectedBooking.booking_ref}</h3>
                </div>
                <StatusBadge status={selectedBooking.status} />
              </div>

              {/* Journey & Train Details */}
              <div>
                <h4 className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Train className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Journey & Timings
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-zinc-50 dark:bg-zinc-800/50 p-3.5 rounded-xl border border-zinc-200/80 dark:border-zinc-800 text-xs">
                  <div>
                    <span className="text-zinc-400 text-[10px]">ROUTE</span>
                    <p className="font-bold text-zinc-900 dark:text-white">{selectedBooking.from_station} ➔ {selectedBooking.to_station}</p>
                  </div>
                  <div>
                    <span className="text-zinc-400 text-[10px]">DATE</span>
                    <p className="font-bold text-zinc-900 dark:text-white">{selectedBooking.journey_date}</p>
                  </div>
                  <div>
                    <span className="text-zinc-400 text-[10px]">TRAIN</span>
                    <p className="font-bold text-zinc-900 dark:text-white">{selectedBooking.train_number || 'N/A'}</p>
                  </div>
                  <div>
                    <span className="text-zinc-400 text-[10px]">CLASS / QUOTA</span>
                    <p className="font-bold text-zinc-900 dark:text-white">{selectedBooking.journey_class} / {selectedBooking.quota}</p>
                  </div>
                </div>
              </div>

              {/* Passenger Manifest */}
              <div>
                <h4 className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Passenger Manifest ({selectedBooking.passenger_count})
                </h4>
                <div className="divide-y divide-zinc-200 dark:divide-zinc-800 border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden">
                  {selectedBooking.passengers && selectedBooking.passengers.length > 0 ? (
                    selectedBooking.passengers.map((p, idx) => (
                      <div key={idx} className="p-3 bg-white dark:bg-zinc-900 flex items-center justify-between text-xs">
                        <div>
                          <p className="font-bold text-zinc-900 dark:text-white">{p.name}</p>
                          <p className="text-[11px] text-zinc-400">{p.age} yrs • {p.gender === 'M' ? 'Male' : p.gender === 'F' ? 'Female' : 'Transgender'} • Pref: {p.berth}</p>
                        </div>
                        <div className="text-right">
                          <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 font-bold text-[11px]">
                            {p.seat || 'Seat TBD'}
                          </span>
                          <p className="text-[10px] text-zinc-400 mt-0.5">{p.status || 'CNF'}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 text-center text-zinc-400 text-xs">No passenger manifest recorded.</div>
                  )}
                </div>
              </div>

              {/* Financial & Notification Dispatch Dossier */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Financial Summary */}
                <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2 text-xs">
                  <h5 className="font-bold text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                    <IndianRupee className="w-3.5 h-3.5 text-emerald-600" /> Financial Summary
                  </h5>
                  <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                    <span>Total Fare:</span>
                    <span className="font-bold text-zinc-900 dark:text-white">Rs. {selectedBooking.fare || 0}</span>
                  </div>
                  <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                    <span>Payment Status:</span>
                    <span className="font-semibold text-emerald-600 dark:text-emerald-400">{selectedBooking.payment_status}</span>
                  </div>
                  <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                    <span>Transaction ID:</span>
                    <span className="font-mono text-[11px]">{selectedBooking.transaction_id || 'N/A'}</span>
                  </div>
                </div>

                {/* Notifications Dispatch */}
                <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-800 space-y-2 text-xs">
                  <h5 className="font-bold text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                    <Send className="w-3.5 h-3.5 text-emerald-600" /> Notifications
                  </h5>
                  <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                    <span>Telegram Bot:</span>
                    <span className={`font-semibold ${selectedBooking.telegram_status === 'SENT' ? 'text-emerald-600' : 'text-zinc-400'}`}>
                      {selectedBooking.telegram_status}
                    </span>
                  </div>
                  <div className="flex justify-between text-zinc-500 dark:text-zinc-400">
                    <span>WhatsApp Cloud:</span>
                    <span className={`font-semibold ${selectedBooking.whatsapp_status === 'SENT' ? 'text-emerald-600' : 'text-zinc-400'}`}>
                      {selectedBooking.whatsapp_status}
                    </span>
                  </div>
                </div>
              </div>

              {/* Notes */}
              <div>
                <h4 className="text-xs font-bold text-zinc-500 dark:text-zinc-400 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                  <FileText className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                  Internal CRM Notes
                </h4>
                <p className="p-3 bg-zinc-50 dark:bg-zinc-800/30 rounded-xl text-xs text-zinc-700 dark:text-zinc-300 border border-zinc-200/60 dark:border-zinc-800">
                  {selectedBooking.notes || 'No notes added for this record yet.'}
                </p>
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center text-zinc-400 text-xs">
              Select a booking from the left to view detailed CRM profile.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
