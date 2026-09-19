import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Trash2, 
  Users, 
  MapPin, 
  Phone, 
  Sliders, 
  ShieldAlert, 
  Play, 
  Train, 
  AlertCircle,
  CheckCircle2,
  Bookmark
} from 'lucide-react';
import { startBooking, fetchPassengers, fetchJourneys } from '../services/api';

export default function NewBooking({ onBookingStarted }) {
  // Form fields
  const [fromStation, setFromStation] = useState('NDLS');
  const [toStation, setToStation] = useState('BPL');
  const [boardingStation, setBoardingStation] = useState('NDLS');
  const [journeyDate, setJourneyDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().split('T')[0];
  });
  const [journeyClass, setJourneyClass] = useState('3A');
  const [quota, setQuota] = useState('GN');
  const [trainPreference, setTrainPreference] = useState('12002');
  const [contactMobile, setContactMobile] = useState('9876543210');
  const [contactEmail, setContactEmail] = useState('user@example.com');
  const [demoMode, setDemoMode] = useState(true);

  // Passengers list
  const [passengers, setPassengers] = useState([
    { name: '', age: 30, gender: 'M', berth_preference: 'NONE', food_preference: 'D' }
  ]);

  // Saved presets
  const [savedPassengers, setSavedPassengers] = useState([]);
  const [savedJourneys, setSavedJourneys] = useState([]);
  
  // Confirmation Modal
  const [showSummaryModal, setShowSummaryModal] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchPassengers().then(setSavedPassengers).catch(() => {});
    fetchJourneys().then(setSavedJourneys).catch(() => {});
  }, []);

  const handleAddPassenger = () => {
    if (passengers.length >= 6) {
      alert('IRCTC allows a maximum of 6 passengers per ticket.');
      return;
    }
    setPassengers([...passengers, { name: '', age: 30, gender: 'M', berth_preference: 'NONE', food_preference: 'D' }]);
  };

  const handleRemovePassenger = (index) => {
    if (passengers.length === 1) return;
    setPassengers(passengers.filter((_, i) => i !== index));
  };

  const updatePassenger = (index, field, value) => {
    const updated = [...passengers];
    updated[index][field] = value;
    setPassengers(updated);
  };

  const applySavedPassenger = (savedP) => {
    // Fill first empty passenger or append
    const emptyIdx = passengers.findIndex((p) => !p.name.trim());
    if (emptyIdx !== -1) {
      const updated = [...passengers];
      updated[emptyIdx] = {
        name: savedP.name,
        age: savedP.age,
        gender: savedP.gender,
        berth_preference: savedP.berth_preference || 'NONE',
        food_preference: savedP.food_preference || 'D',
      };
      setPassengers(updated);
    } else if (passengers.length < 6) {
      setPassengers([
        ...passengers,
        {
          name: savedP.name,
          age: savedP.age,
          gender: savedP.gender,
          berth_preference: savedP.berth_preference || 'NONE',
          food_preference: savedP.food_preference || 'D',
        }
      ]);
    }
  };

  const applySavedJourney = (j) => {
    setFromStation(j.from_station);
    setToStation(j.to_station);
    setBoardingStation(j.boarding_station || j.from_station);
    if (j.preferred_class) setJourneyClass(j.preferred_class);
    if (j.preferred_quota) setQuota(j.preferred_quota);
    if (j.train_preference) setTrainPreference(j.train_preference);
  };

  const handleReviewClick = (e) => {
    e.preventDefault();
    setErrorMsg(null);

    // Validate
    if (!fromStation.trim() || !toStation.trim()) {
      setErrorMsg('Please specify origin and destination stations.');
      return;
    }
    for (let p of passengers) {
      if (!p.name.trim()) {
        setErrorMsg('Please enter a name for all passengers.');
        return;
      }
    }
    setShowSummaryModal(true);
  };

  const handleConfirmAndStart = async (allowDuplicate = false) => {
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const isDuplicateAllowed = typeof allowDuplicate === 'boolean' ? allowDuplicate : false;
      const payload = {
        from_station: fromStation,
        to_station: toStation,
        boarding_station: boardingStation,
        journey_date: journeyDate,
        journey_class: journeyClass,
        quota: quota,
        train_preference: trainPreference,
        contact_mobile: contactMobile,
        contact_email: contactEmail,
        passengers: passengers,
        demo_mode: demoMode,
        allow_duplicate: isDuplicateAllowed
      };

      const res = await startBooking(payload);
      setShowSummaryModal(false);
      onBookingStarted(res.booking_ref);
    } catch (err) {
      setErrorMsg(err.message || 'Failed to initiate booking.');
      setShowSummaryModal(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in pb-12">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Prepare New Ticket Booking</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
          Configure journey details, passengers, and automation boundaries.
        </p>
      </div>

      {errorMsg && (
        <div className="p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded-xl space-y-3">
          <div className="flex items-center gap-3 text-xs text-rose-700 dark:text-rose-300">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span className="font-medium">{errorMsg}</span>
          </div>
          {errorMsg.includes('Duplicate booking protection') && (
            <div className="pt-2 border-t border-rose-200/60 dark:border-rose-900 flex items-center gap-2">
              <button
                type="button"
                onClick={() => handleConfirmAndStart(true)}
                disabled={submitting}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-lg shadow-xs transition-colors cursor-pointer disabled:opacity-50"
              >
                {submitting ? 'Starting...' : 'Book Another Ticket Anyway (Ignore Warning)'}
              </button>
              <span className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Click this if you deliberately want to book another ticket for the same route & date.
              </span>
            </div>
          )}
        </div>
      )}

      {/* Saved Journeys Quick Pill Bar */}
      {savedJourneys.length > 0 && (
        <div className="bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/60 rounded-xl p-3 flex items-center gap-2 overflow-x-auto text-xs">
          <Bookmark className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
          <span className="font-semibold text-emerald-800 dark:text-emerald-300 shrink-0">Saved Routes:</span>
          {savedJourneys.map((j) => (
            <button
              key={j.id}
              onClick={() => applySavedJourney(j)}
              className="px-3 py-1 bg-white dark:bg-zinc-800 hover:bg-emerald-100 dark:hover:bg-emerald-900/60 text-zinc-700 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700 rounded-lg text-xs font-medium shrink-0 transition-colors cursor-pointer"
            >
              {j.label} ({j.from_station} ➔ {j.to_station})
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleReviewClick} className="space-y-6">
        {/* Section 1: Journey Details */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-100 dark:border-zinc-800 pb-3">
            <MapPin className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h3 className="font-bold text-sm text-zinc-900 dark:text-white">1. Journey Information</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">From Station</label>
              <input
                type="text"
                value={fromStation}
                onChange={(e) => setFromStation(e.target.value.toUpperCase())}
                placeholder="e.g. NDLS or NEW DELHI"
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">To Station</label>
              <input
                type="text"
                value={toStation}
                onChange={(e) => setToStation(e.target.value.toUpperCase())}
                placeholder="e.g. BPL or BHOPAL"
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Journey Date</label>
              <input
                type="date"
                value={journeyDate}
                onChange={(e) => setJourneyDate(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Class</label>
              <select
                value={journeyClass}
                onChange={(e) => setJourneyClass(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              >
                <option value="1A">AC First Class (1A)</option>
                <option value="2A">AC 2 Tier (2A)</option>
                <option value="3A">AC 3 Tier (3A)</option>
                <option value="3E">AC 3 Economy (3E)</option>
                <option value="CC">AC Chair Car (CC)</option>
                <option value="EC">Exec. Chair Car (EC)</option>
                <option value="SL">Sleeper (SL)</option>
                <option value="2S">Second Sitting (2S)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Quota</label>
              <select
                value={quota}
                onChange={(e) => setQuota(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              >
                <option value="GN">General (GN)</option>
                <option value="TQ">Tatkal (TQ)</option>
                <option value="PT">Premium Tatkal (PT)</option>
                <option value="LD">Ladies (LD)</option>
                <option value="SS">Senior Citizen (SS)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Preferred Train No.</label>
              <input
                type="text"
                value={trainPreference}
                onChange={(e) => setTrainPreference(e.target.value)}
                placeholder="e.g. 12002"
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Passengers */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">
                2. Passenger Information ({passengers.length}/6)
              </h3>
            </div>

            {savedPassengers.length > 0 && (
              <div className="flex items-center gap-1.5 overflow-x-auto">
                <span className="text-[11px] text-zinc-400 font-medium">Quick load:</span>
                {savedPassengers.slice(0, 3).map((sp) => (
                  <button
                    key={sp.id}
                    type="button"
                    onClick={() => applySavedPassenger(sp)}
                    className="px-2.5 py-0.5 text-[11px] bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 rounded-md transition-colors cursor-pointer"
                  >
                    + {sp.name.split(' ')[0]}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-3">
            {passengers.map((p, idx) => (
              <div
                key={idx}
                className="p-4 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl border border-zinc-200/80 dark:border-zinc-800 grid grid-cols-1 sm:grid-cols-12 gap-3 items-center"
              >
                <div className="sm:col-span-4">
                  <label className="block text-[11px] font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">
                    Passenger {idx + 1} Name
                  </label>
                  <input
                    type="text"
                    value={p.name}
                    onChange={(e) => updatePassenger(idx, 'name', e.target.value)}
                    placeholder="Full name as on Aadhaar/Govt ID"
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white focus:outline-emerald-500"
                    required
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-[11px] font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">Age</label>
                  <input
                    type="number"
                    min="1"
                    max="120"
                    value={p.age}
                    onChange={(e) => updatePassenger(idx, 'age', parseInt(e.target.value) || 1)}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white focus:outline-emerald-500"
                    required
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="block text-[11px] font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">Gender</label>
                  <select
                    value={p.gender}
                    onChange={(e) => updatePassenger(idx, 'gender', e.target.value)}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  >
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                    <option value="T">Transgender</option>
                  </select>
                </div>

                <div className="sm:col-span-3">
                  <label className="block text-[11px] font-medium text-zinc-500 dark:text-zinc-400 mb-0.5">Berth Preference</label>
                  <select
                    value={p.berth_preference}
                    onChange={(e) => updatePassenger(idx, 'berth_preference', e.target.value)}
                    className="w-full px-2 py-1.5 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-white focus:outline-emerald-500"
                  >
                    <option value="NONE">No Preference</option>
                    <option value="LB">Lower Berth</option>
                    <option value="MB">Middle Berth</option>
                    <option value="UB">Upper Berth</option>
                    <option value="SL">Side Lower</option>
                    <option value="SU">Side Upper</option>
                  </select>
                </div>

                <div className="sm:col-span-1 flex justify-end">
                  {passengers.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemovePassenger(idx)}
                      className="p-1.5 text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg transition-colors cursor-pointer"
                      title="Remove passenger"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}

            <button
              type="button"
              onClick={handleAddPassenger}
              className="w-full py-2.5 border border-dashed border-zinc-300 dark:border-zinc-700 hover:border-emerald-500 rounded-xl text-xs font-semibold text-zinc-600 dark:text-zinc-400 hover:text-emerald-600 dark:hover:text-emerald-400 flex items-center justify-center gap-2 transition-all cursor-pointer"
            >
              <Plus className="w-4 h-4" /> Add Another Passenger
            </button>
          </div>
        </div>

        {/* Section 3: Contact & Preferences */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 border-b border-zinc-100 dark:border-zinc-800 pb-3">
            <Phone className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            <h3 className="font-bold text-sm text-zinc-900 dark:text-white">3. Contact & Execution Mode</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Mobile Number (SMS alerts)</label>
              <input
                type="tel"
                value={contactMobile}
                onChange={(e) => setContactMobile(e.target.value)}
                placeholder="10-digit mobile number"
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Email ID</label>
              <input
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="Your official email for e-ticket"
                className="w-full px-3 py-2 text-xs rounded-xl border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-zinc-900 dark:text-white focus:outline-emerald-500"
              />
            </div>
          </div>

          {/* Mode Selector (Demo Mode vs Live) */}
          <div className="mt-4 p-4 rounded-xl border border-emerald-500/30 bg-emerald-50/30 dark:bg-emerald-950/20 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold text-emerald-900 dark:text-emerald-300">
                {demoMode ? 'Safe Mock / Demo Mode Active' : 'Live Official IRCTC Mode Active'}
              </p>
              <p className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">
                {demoMode 
                  ? 'Simulates entire end-to-end booking, manual pauses, CRM, and Excel without placing real IRCTC orders.' 
                  : 'Automates browser on official irctc.co.in with manual security & payment handoffs.'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setDemoMode(!demoMode)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-all ${
                demoMode 
                  ? 'bg-emerald-600 text-white shadow-xs' 
                  : 'bg-amber-600 text-white shadow-xs'
              }`}
            >
              {demoMode ? 'Using Demo' : 'Using Live IRCTC'}
            </button>
          </div>
        </div>

        {/* Submit Review Trigger */}
        <div className="flex justify-end">
          <button
            type="submit"
            className="px-8 py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-sm rounded-xl shadow-lg shadow-emerald-600/30 flex items-center gap-2 cursor-pointer transition-all"
          >
            <Play className="w-4 h-4" /> Review & Start Booking
          </button>
        </div>
      </form>

      {/* Confirmation & Summary Modal (Mandatory as per section 21) */}
      {showSummaryModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
            <div className="bg-emerald-600 px-6 py-4 text-white">
              <h3 className="text-base font-bold">Booking Confirmation Summary</h3>
              <p className="text-xs text-white/80">Please review before starting automation</p>
            </div>

            <div className="p-6 space-y-4 text-xs">
              <div className="p-3 bg-zinc-50 dark:bg-zinc-800 rounded-xl space-y-2">
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Route:</span>
                  <span className="font-bold text-zinc-900 dark:text-white">{fromStation} ➔ {toStation}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Date:</span>
                  <span className="font-semibold text-zinc-900 dark:text-white">{journeyDate}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Class & Quota:</span>
                  <span className="font-semibold text-zinc-900 dark:text-white">{journeyClass} | {quota}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Passengers ({passengers.length}):</span>
                  <span className="font-semibold text-zinc-900 dark:text-white">{passengers.map(p => p.name).join(', ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Mode:</span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">{demoMode ? 'Safe Mock Demo' : 'Live IRCTC'}</span>
                </div>
              </div>

              <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl text-[11px] text-amber-800 dark:text-amber-300">
                <p className="font-semibold flex items-center gap-1 mb-1">
                  <ShieldAlert className="w-3.5 h-3.5" /> Security Handover Notice
                </p>
                <p>The system will pause whenever CAPTCHA, OTP, or Payment is required. You will complete those steps in the browser.</p>
              </div>
            </div>

            <div className="px-6 py-4 bg-zinc-50 dark:bg-zinc-800/50 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowSummaryModal(false)}
                className="px-4 py-2 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 rounded-lg cursor-pointer"
              >
                Back to Edit
              </button>
              <button
                type="button"
                onClick={() => handleConfirmAndStart(false)}
                disabled={submitting}
                className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-md shadow-emerald-600/20 flex items-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {submitting ? 'Starting...' : 'Confirm & Launch Assistant'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
