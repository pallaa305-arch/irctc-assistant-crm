import React, { useState, useEffect } from 'react';
import { 
  UserCheck, 
  Plus, 
  Trash2, 
  Edit3, 
  Check, 
  X, 
  Star,
  Users
} from 'lucide-react';
import { fetchPassengers, createPassenger, updatePassenger, deletePassenger } from '../services/api';

export default function Passengers() {
  const [passengers, setPassengers] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Modal / Form state
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    age: 30,
    gender: 'M',
    berth_preference: 'NONE',
    food_preference: 'D',
    senior_citizen: false,
    is_default: false,
  });

  const loadPassengers = async () => {
    setLoading(true);
    try {
      const data = await fetchPassengers();
      setPassengers(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPassengers();
  }, []);

  const handleOpenAdd = () => {
    setEditingId(null);
    setFormData({
      name: '',
      age: 30,
      gender: 'M',
      berth_preference: 'NONE',
      food_preference: 'D',
      senior_citizen: false,
      is_default: false,
    });
    setShowModal(true);
  };

  const handleOpenEdit = (p) => {
    setEditingId(p.id);
    setFormData({
      name: p.name,
      age: p.age,
      gender: p.gender,
      berth_preference: p.berth_preference || 'NONE',
      food_preference: p.food_preference || 'D',
      senior_citizen: p.senior_citizen || false,
      is_default: p.is_default || false,
    });
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingId) {
        await updatePassenger(editingId, formData);
      } else {
        await createPassenger(formData);
      }
      setShowModal(false);
      loadPassengers();
    } catch (err) {
      alert('Error saving passenger: ' + err.message);
    }
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete profile for ${name}?`)) return;
    try {
      await deletePassenger(id);
      loadPassengers();
    } catch (err) {
      alert('Error deleting passenger: ' + err.message);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Passenger Master Profiles</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Frequently booked passengers for instant autofill during booking ({passengers.length})
          </p>
        </div>

        <button
          onClick={handleOpenAdd}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs rounded-xl shadow-md shadow-emerald-600/20 flex items-center gap-2 cursor-pointer transition-colors"
        >
          <Plus className="w-4 h-4" /> Add New Passenger
        </button>
      </div>

      {/* Grid of Passenger Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {passengers.map((p) => (
          <div
            key={p.id}
            className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 font-bold text-xs flex items-center justify-center">
                    {p.name.charAt(0)}
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-zinc-900 dark:text-white">{p.name}</h3>
                    <p className="text-[11px] text-zinc-400">
                      {p.age} yrs • {p.gender === 'M' ? 'Male' : p.gender === 'F' ? 'Female' : 'Transgender'}
                    </p>
                  </div>
                </div>
                {p.is_default && (
                  <span className="p-1 text-amber-500" title="Frequent / Default Traveler">
                    <Star className="w-4 h-4 fill-amber-400" />
                  </span>
                )}
              </div>

              <div className="mt-4 pt-3 border-t border-zinc-100 dark:border-zinc-800 grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-zinc-400">Berth Pref:</span>
                  <p className="font-semibold text-zinc-700 dark:text-zinc-300">{p.berth_preference || 'None'}</p>
                </div>
                <div>
                  <span className="text-zinc-400">Food Pref:</span>
                  <p className="font-semibold text-zinc-700 dark:text-zinc-300">
                    {p.food_preference === 'V' ? 'Veg' : p.food_preference === 'N' ? 'Non-Veg' : 'No Food'}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-zinc-100 dark:border-zinc-800 flex items-center justify-end gap-2">
              <button
                onClick={() => handleOpenEdit(p)}
                className="p-1.5 text-zinc-500 hover:text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 rounded-lg transition-colors cursor-pointer"
                title="Edit profile"
              >
                <Edit3 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => handleDelete(p.id, p.name)}
                className="p-1.5 text-zinc-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 rounded-lg transition-colors cursor-pointer"
                title="Delete profile"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}

        {passengers.length === 0 && !loading && (
          <div className="col-span-full py-16 text-center text-zinc-400 border border-dashed border-zinc-200 dark:border-zinc-800 rounded-2xl">
            <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-xs">No passenger profiles saved yet.</p>
            <button
              onClick={handleOpenAdd}
              className="mt-3 text-emerald-600 font-semibold text-xs cursor-pointer"
            >
              + Add your first passenger profile
            </button>
          </div>
        )}
      </div>

      {/* Add / Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">
                {editingId ? 'Edit Passenger' : 'Add Passenger Profile'}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-zinc-400 hover:text-zinc-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="As per official Govt ID"
                  className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Age</label>
                  <input
                    type="number"
                    min="1"
                    max="120"
                    required
                    value={formData.age}
                    onChange={(e) => setFormData({ ...formData, age: parseInt(e.target.value) || 1 })}
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  />
                </div>

                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Gender</label>
                  <select
                    value={formData.gender}
                    onChange={(e) => setFormData({ ...formData, gender: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  >
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                    <option value="T">Transgender</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Berth Preference</label>
                  <select
                    value={formData.berth_preference}
                    onChange={(e) => setFormData({ ...formData, berth_preference: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  >
                    <option value="NONE">No Preference</option>
                    <option value="LB">Lower Berth</option>
                    <option value="MB">Middle Berth</option>
                    <option value="UB">Upper Berth</option>
                    <option value="SL">Side Lower</option>
                    <option value="SU">Side Upper</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Food Preference</label>
                  <select
                    value={formData.food_preference}
                    onChange={(e) => setFormData({ ...formData, food_preference: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  >
                    <option value="D">No Food</option>
                    <option value="V">Veg</option>
                    <option value="N">Non-Veg</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center gap-4 pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.is_default}
                    onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                    className="rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span className="text-zinc-700 dark:text-zinc-300">Default Traveler</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={formData.senior_citizen}
                    onChange={(e) => setFormData({ ...formData, senior_citizen: e.target.checked })}
                    className="rounded text-emerald-600 focus:ring-emerald-500"
                  />
                  <span className="text-zinc-700 dark:text-zinc-300">Senior Citizen</span>
                </label>
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
                  {editingId ? 'Update Profile' : 'Save Profile'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
