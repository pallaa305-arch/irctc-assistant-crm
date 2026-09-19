import React, { useState, useEffect } from 'react';
import { 
  MapPin, 
  Plus, 
  Trash2, 
  ArrowRight, 
  Compass, 
  Train, 
  X,
  CheckCircle2
} from 'lucide-react';
import { fetchJourneys, createJourney, deleteJourney } from '../services/api';

export default function SavedJourneys({ setTab }) {
  const [journeys, setJourneys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    label: '',
    from_station: '',
    to_station: '',
    boarding_station: '',
    train_preference: '',
    preferred_class: '3A',
    preferred_quota: 'GN',
  });

  const loadJourneys = async () => {
    setLoading(true);
    try {
      const data = await fetchJourneys();
      setJourneys(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJourneys();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await createJourney(formData);
      setShowModal(false);
      setFormData({
        label: '',
        from_station: '',
        to_station: '',
        boarding_station: '',
        train_preference: '',
        preferred_class: '3A',
        preferred_quota: 'GN',
      });
      loadJourneys();
    } catch (err) {
      alert('Failed saving journey: ' + err.message);
    }
  };

  const handleDelete = async (id, label) => {
    if (!window.confirm(`Delete saved route "${label}"?`)) return;
    try {
      await deleteJourney(id);
      loadJourneys();
    } catch (err) {
      alert('Error: ' + err.message);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Saved Journey Routes</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Store routine corridors for 1-click booking setup ({journeys.length})
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-2 cursor-pointer transition-colors"
        >
          <Plus className="w-4 h-4" /> Save New Route
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {journeys.map((j) => (
          <div
            key={j.id}
            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-bold text-sm text-zinc-900 dark:text-white">{j.label}</h3>
                  <div className="flex items-center gap-1.5 font-bold text-xs text-emerald-600 dark:text-emerald-400 mt-1">
                    <span>{j.from_station}</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                    <span>{j.to_station}</span>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(j.id, j.label)}
                  className="p-1.5 text-zinc-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg transition-colors cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-100 dark:border-zinc-800 grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-zinc-400">Class & Quota:</span>
                  <p className="font-semibold text-zinc-700 dark:text-zinc-300">{j.preferred_class} | {j.preferred_quota}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Train Pref:</span>
                  <p className="font-semibold text-zinc-700 dark:text-zinc-300">{j.train_preference || 'Any Train'}</p>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-zinc-100 dark:border-zinc-800">
              <button
                onClick={() => setTab('new-booking')}
                className="w-full py-2 bg-zinc-50 dark:bg-zinc-800/80 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 text-zinc-700 dark:text-zinc-300 hover:text-emerald-600 dark:hover:text-emerald-400 font-semibold text-xs rounded-xl border border-zinc-200/80 dark:border-zinc-700 transition-colors cursor-pointer flex items-center justify-center gap-1.5"
              >
                <Train className="w-3.5 h-3.5" /> Book This Journey
              </button>
            </div>
          </div>
        ))}

        {journeys.length === 0 && !loading && (
          <div className="col-span-full py-16 text-center text-zinc-400 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl">
            <Compass className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-xs">No journey presets saved yet.</p>
            <button
              onClick={() => setShowModal(true)}
              className="mt-3 text-emerald-600 font-semibold text-xs cursor-pointer"
            >
              + Save your frequent route
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">Save Frequent Journey</h3>
              <button onClick={() => setShowModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Route Nickname</label>
                <input
                  type="text"
                  required
                  value={formData.label}
                  onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                  placeholder="e.g. Home to Parents / Office Commute"
                  className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">From Station</label>
                  <input
                    type="text"
                    required
                    value={formData.from_station}
                    onChange={(e) => setFormData({ ...formData, from_station: e.target.value.toUpperCase() })}
                    placeholder="e.g. NDLS"
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">To Station</label>
                  <input
                    type="text"
                    required
                    value={formData.to_station}
                    onChange={(e) => setFormData({ ...formData, to_station: e.target.value.toUpperCase() })}
                    placeholder="e.g. BPL"
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Preferred Class</label>
                  <select
                    value={formData.preferred_class}
                    onChange={(e) => setFormData({ ...formData, preferred_class: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  >
                    <option value="1A">1A</option>
                    <option value="2A">2A</option>
                    <option value="3A">3A</option>
                    <option value="SL">SL</option>
                    <option value="CC">CC</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Preferred Quota</label>
                  <select
                    value={formData.preferred_quota}
                    onChange={(e) => setFormData({ ...formData, preferred_quota: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  >
                    <option value="GN">General (GN)</option>
                    <option value="TQ">Tatkal (TQ)</option>
                    <option value="PT">Premium Tatkal (PT)</option>
                    <option value="LD">Ladies (LD)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Train Number Preference (Optional)</label>
                <input
                  type="text"
                  value={formData.train_preference}
                  onChange={(e) => setFormData({ ...formData, train_preference: e.target.value })}
                  placeholder="e.g. 12002"
                  className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t border-zinc-100 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-lg cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs cursor-pointer"
                >
                  Save Route
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
