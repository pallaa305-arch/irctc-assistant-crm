import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  Download, 
  FileSpreadsheet, 
  RefreshCw, 
  Trash2, 
  Edit3, 
  Eye, 
  Train,
  Check
} from 'lucide-react';
import { fetchBookings, updateBookingCRM, deleteBookingCRM } from '../services/api';
import StatusBadge from '../components/StatusBadge';

export default function BookingHistory({ onSelectBookingForTracking }) {
  const [bookings, setBookings] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [classFilter, setClassFilter] = useState('ALL');
  
  // Edit note modal
  const [editingBooking, setEditingBooking] = useState(null);
  const [noteText, setNoteText] = useState('');

  const loadBookings = async () => {
    setLoading(true);
    try {
      const data = await fetchBookings({
        q: searchTerm,
        status: statusFilter,
        journey_class: classFilter,
        limit: 100
      });
      setBookings(data.items);
      setTotal(data.total);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBookings();
  }, [statusFilter, classFilter]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadBookings();
  };

  const handleSaveNote = async () => {
    if (!editingBooking) return;
    try {
      await updateBookingCRM(editingBooking.id, { notes: noteText });
      setEditingBooking(null);
      loadBookings();
    } catch (err) {
      alert('Failed saving note: ' + err.message);
    }
  };

  const handleDelete = async (id, ref) => {
    if (!window.confirm(`Are you sure you want to delete booking record ${ref}?`)) return;
    try {
      await deleteBookingCRM(id);
      loadBookings();
    } catch (err) {
      alert('Delete failed: ' + err.message);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Booking History</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Search, filter, manage notes, and export historical bookings ({total} total)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <a
            href="/api/crm/export/excel"
            download
            className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-xl shadow-xs flex items-center gap-2 transition-colors cursor-pointer"
          >
            <FileSpreadsheet className="w-4 h-4" /> Export Excel
          </a>
          <a
            href="/api/crm/export/csv"
            download
            className="px-3.5 py-2 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-200 text-xs font-semibold rounded-xl border border-zinc-200 dark:border-zinc-700 flex items-center gap-2 transition-colors cursor-pointer"
          >
            <Download className="w-4 h-4" /> CSV
          </a>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-4 shadow-xs flex flex-col md:flex-row items-center gap-3">
        <form onSubmit={handleSearchSubmit} className="flex-1 w-full flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by PNR, Reference ID, Station, or Train..."
              className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-zinc-900 dark:bg-white text-white dark:text-zinc-900 text-xs font-semibold rounded-xl cursor-pointer"
          >
            Search
          </button>
        </form>

        <div className="flex items-center gap-2 w-full md:w-auto">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
          >
            <option value="ALL">All Statuses</option>
            <option value="CONFIRMED">Confirmed</option>
            <option value="WAITING_MANUAL">Action Required</option>
            <option value="PAYMENT_PENDING">Payment Pending</option>
            <option value="FAILED">Failed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>

          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
          >
            <option value="ALL">All Classes</option>
            <option value="1A">1A</option>
            <option value="2A">2A</option>
            <option value="3A">3A</option>
            <option value="SL">SL</option>
            <option value="CC">CC</option>
          </select>

          <button
            onClick={loadBookings}
            className="p-2 bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-xl text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 cursor-pointer"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Bookings Table */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-zinc-50 dark:bg-zinc-800/60 border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 dark:text-zinc-400 font-semibold">
              <tr>
                <th className="py-3.5 px-4">Booking Ref</th>
                <th className="py-3.5 px-4">PNR / Txn</th>
                <th className="py-3.5 px-4">Route & Date</th>
                <th className="py-3.5 px-4">Train & Class</th>
                <th className="py-3.5 px-4">Passengers</th>
                <th className="py-3.5 px-4">Fare</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Notes</th>
                <th className="py-3.5 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200/60 dark:divide-zinc-800 text-zinc-800 dark:text-zinc-200">
              {bookings.length > 0 ? (
                bookings.map((b) => (
                  <tr key={b.id} className="hover:bg-zinc-50/70 dark:hover:bg-zinc-800/40 transition-colors">
                    <td className="py-3.5 px-4 font-mono font-medium text-emerald-600 dark:text-emerald-400">
                      {b.booking_ref}
                    </td>
                    <td className="py-3.5 px-4">
                      <p className="font-mono font-bold text-zinc-900 dark:text-white">{b.pnr || '—'}</p>
                      <p className="text-[10px] text-zinc-400 font-mono">{b.transaction_id || ''}</p>
                    </td>
                    <td className="py-3.5 px-4">
                      <p className="font-semibold text-zinc-900 dark:text-white">{b.from_station} ➔ {b.to_station}</p>
                      <p className="text-[11px] text-zinc-400">{b.journey_date}</p>
                    </td>
                    <td className="py-3.5 px-4">
                      <p className="font-medium">{b.train_number ? `${b.train_number} ${b.train_name || ''}` : 'Any Train'}</p>
                      <p className="text-[10px] text-zinc-400">{b.journey_class} | {b.quota}</p>
                    </td>
                    <td className="py-3.5 px-4">
                      <p className="font-medium">{b.passenger_count} Pax</p>
                      <p className="text-[10px] text-zinc-400 truncate max-w-[120px]">
                        {b.passengers.map(p => p.name).join(', ')}
                      </p>
                    </td>
                    <td className="py-3.5 px-4 font-semibold">
                      ₹{b.fare ? b.fare.toLocaleString('en-IN') : '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      <StatusBadge status={b.status} />
                    </td>
                    <td className="py-3.5 px-4 text-[11px] text-zinc-500 max-w-[140px] truncate">
                      {b.notes || '—'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => onSelectBookingForTracking(b.booking_ref)}
                          className="p-1.5 text-zinc-500 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg transition-colors cursor-pointer"
                          title="Track booking state"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingBooking(b);
                            setNoteText(b.notes || '');
                          }}
                          className="p-1.5 text-zinc-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40 rounded-lg transition-colors cursor-pointer"
                          title="Edit CRM Note"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(b.id, b.booking_ref)}
                          className="p-1.5 text-zinc-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer"
                          title="Delete record"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="9" className="py-12 text-center text-zinc-400 text-xs">
                    No booking records found matching your filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Edit Note Modal */}
      {editingBooking && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <h3 className="font-bold text-sm text-zinc-900 dark:text-white">
              Edit CRM Note for {editingBooking.booking_ref}
            </h3>
            <textarea
              rows="4"
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder="Add personal notes, client expense tags, or trip reasons..."
              className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setEditingBooking(null)}
                className="px-4 py-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveNote}
                className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs cursor-pointer flex items-center gap-1.5"
              >
                <Check className="w-4 h-4" /> Save Note
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
