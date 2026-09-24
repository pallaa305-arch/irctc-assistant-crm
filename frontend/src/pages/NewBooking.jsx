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
  Bookmark,
  Clock,
  ArrowRight,
  Loader2,
  Sparkles,
  Zap,
  Filter,
  ArrowLeftRight
} from 'lucide-react';
import { startBooking, fetchPassengers, fetchJourneys, searchTrains } from '../services/api';
import StationSelector from '../components/StationSelector';
import ModernDatePicker from '../components/ModernDatePicker';

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

  // Timing filter & Auto-fetched trains on selected route
  const [timingFilter, setTimingFilter] = useState('ALL');
  const [routeTrains, setRouteTrains] = useState([]);
  const [loadingTrains, setLoadingTrains] = useState(false);
  const [selectedTrainObj, setSelectedTrainObj] = useState(null);

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

  // Auto-fetch trains and timings whenever route changes
  useEffect(() => {
    const f = (fromStation || '').trim();
    const t = (toStation || '').trim();
    if (f.length >= 2 && t.length >= 2) {
      setLoadingTrains(true);
      const timer = setTimeout(() => {
        searchTrains(f, t)
          .then((res) => {
            const list = res.trains || [];
            setRouteTrains(list);
            if (list.length > 0) {
              const currentMatch = list.find((item) => item.train_number === trainPreference);
              if (currentMatch) {
                setSelectedTrainObj(currentMatch);
              } else {
                setSelectedTrainObj(list[0]);
                setTrainPreference(list[0].train_number);
                if (list[0].classes && !list[0].classes.includes(journeyClass)) {
                  setJourneyClass(list[0].classes[0]);
                }
              }
            } else {
              setSelectedTrainObj(null);
            }
          })
          .catch(() => {
            setRouteTrains([]);
            setSelectedTrainObj(null);
          })
          .finally(() => setLoadingTrains(false));
      }, 350);
      return () => clearTimeout(timer);
    } else {
      setRouteTrains([]);
      setSelectedTrainObj(null);
    }
  }, [fromStation, toStation]);

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

  const selectTrain = (train, targetClass = null) => {
    setTrainPreference(train.train_number);
    setSelectedTrainObj(train);
    if (targetClass) {
      setJourneyClass(targetClass);
    } else if (train.classes && !train.classes.includes(journeyClass)) {
      setJourneyClass(train.classes[0]);
    }
  };

  const handleSwapStations = () => {
    const prevFrom = fromStation;
    setFromStation(toStation);
    setToStation(prevFrom);
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
    if (fromStation.trim().toUpperCase() === toStation.trim().toUpperCase()) {
      setErrorMsg('Origin and destination stations cannot be the same.');
      return;
    }
    if (!journeyDate) {
      setErrorMsg('Please select a journey date.');
      return;
    }
    if (passengers.length === 0) {
      setErrorMsg('At least one passenger is required.');
      return;
    }
    for (let i = 0; i < passengers.length; i++) {
      const p = passengers[i];
      if (!p.name.trim()) {
        setErrorMsg(`Passenger #${i + 1} name is required.`);
        return;
      }
      if (!p.age || p.age < 1 || p.age > 125) {
        setErrorMsg(`Passenger #${i + 1} age must be between 1 and 125.`);
        return;
      }
    }
    if (!contactMobile || contactMobile.length < 10) {
      setErrorMsg('Valid 10-digit mobile number is required.');
      return;
    }

    setShowSummaryModal(true);
  };

  const handleConfirmAndStart = async (forceDuplicate = false) => {
    setSubmitting(true);
    setErrorMsg(null);

    try {
      const payload = {
        from_station: fromStation.trim().toUpperCase(),
        to_station: toStation.trim().toUpperCase(),
        boarding_station: (boardingStation || fromStation).trim().toUpperCase(),
        journey_date: journeyDate,
        journey_class: journeyClass,
        quota: quota,
        train_preference: (trainPreference || '').trim() || undefined,
        contact_mobile: contactMobile.trim(),
        contact_email: (contactEmail || '').trim() || undefined,
        auto_pay: true,
        force_duplicate: forceDuplicate,
        passengers: passengers.map((p) => ({
          name: p.name.trim().toUpperCase(),
          age: parseInt(p.age, 10),
          gender: p.gender,
          berth_preference: p.berth_preference,
          food_preference: p.food_preference,
        })),
      };

      const res = await startBooking(payload);
      setShowSummaryModal(false);
      if (onBookingStarted) {
        onBookingStarted(res.booking_ref || res.booking_id);
      }
    } catch (err) {
      setErrorMsg(err.message || 'Failed to start booking');
      setShowSummaryModal(false);
    } finally {
      setSubmitting(false);
    }
  };

  const TIMING_FILTERS = [
    { id: 'ALL', label: 'All Trains' },
    { id: 'morning', label: '🌅 Morning (06-12)' },
    { id: 'afternoon', label: '☀️ Afternoon (12-18)' },
    { id: 'evening', label: '🌆 Evening (18-24)' },
    { id: 'night', label: '🌙 Night (00-06)' },
    { id: 'tatkal', label: '⚡ Tatkal Ready' },
  ];

  // Filtered route trains based on morning/evening/all
  const filteredTrains = routeTrains.filter((tr) => {
    if (timingFilter === 'ALL') return true;
    return tr.timing_slot === timingFilter;
  });

  const selectedCoach = selectedTrainObj?.coaches?.find((c) => c.class_code === journeyClass) || selectedTrainObj?.coaches?.[0];
  const passengerCount = passengers.length;
  const farePerPerson = selectedCoach?.fare || 0;
  const totalEstimatedFare = farePerPerson * passengerCount;

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-fade-in pb-12">
      <div>
        <h2 className="text-2xl font-bold text-zinc-900 dark:text-white">Prepare New Ticket Booking</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
          Configure journey details, live station lookup, passengers, and automation boundaries.
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
        {/* Section 1: Journey Details (Glass Panel) */}
        <div className="relative z-20 glass-panel rounded-2xl p-6 shadow-lg border border-zinc-200/70 dark:border-white/10 space-y-5">
          <div className="flex items-center justify-between border-b border-zinc-200/60 dark:border-zinc-800/80 pb-3.5">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                <MapPin className="w-4 h-4" />
              </div>
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">1. Journey Information</h3>
            </div>
            <span className="text-[11px] text-zinc-400">
              Live Indian Railways Resolution
            </span>
          </div>

          {/* Row 1: Station Selector with Swap Button */}
          <div className="grid grid-cols-1 sm:grid-cols-12 gap-3 items-end">
            <div className="sm:col-span-5">
              <StationSelector
                label="From Station"
                value={fromStation}
                onChange={setFromStation}
                placeholder="Search station or state (e.g. Rajasthan, NDLS)..."
                required
              />
            </div>

            <div className="sm:col-span-2 flex justify-center pb-0.5">
              <button
                type="button"
                onClick={handleSwapStations}
                title="Swap From and To stations"
                className="w-11 h-11 rounded-xl bg-zinc-100/80 hover:bg-emerald-50 text-zinc-600 hover:text-emerald-600 dark:bg-zinc-800/80 dark:hover:bg-zinc-700 dark:text-zinc-300 border border-zinc-200/80 dark:border-zinc-700/80 flex items-center justify-center transition-all duration-200 hover:scale-105 active:scale-95 shadow-xs cursor-pointer backdrop-blur-md"
              >
                <ArrowLeftRight className="w-4 h-4" />
              </button>
            </div>

            <div className="sm:col-span-5">
              <StationSelector
                label="To Station"
                value={toStation}
                onChange={setToStation}
                placeholder="Search station or state (e.g. Mumbai, BPL)..."
                required
              />
            </div>
          </div>

          {/* Row 2: Modern Date Picker + Class + Quota + Preferred Train */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 pt-1">
            <div className="sm:col-span-1 md:col-span-2">
              <ModernDatePicker
                label="Journey Date"
                value={journeyDate}
                onChange={setJourneyDate}
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1">Class</label>
              <select
                value={journeyClass}
                onChange={(e) => setJourneyClass(e.target.value)}
                className="w-full h-11 px-3 py-2 text-xs font-semibold rounded-xl border border-zinc-200 dark:border-zinc-700/80 bg-zinc-50/90 dark:bg-zinc-900/80 text-zinc-900 dark:text-white focus:outline-emerald-500 shadow-xs cursor-pointer"
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
              <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1 flex items-center justify-between">
                <span>Quota</span>
                {quota === 'TQ' && (
                  <span className="text-[10px] font-bold text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded">
                    ⚡ Tatkal
                  </span>
                )}
              </label>
              <select
                value={quota}
                onChange={(e) => setQuota(e.target.value)}
                className="w-full h-11 px-3 py-2 text-xs font-semibold rounded-xl border border-zinc-200 dark:border-zinc-700/80 bg-zinc-50/90 dark:bg-zinc-900/80 text-zinc-900 dark:text-white focus:outline-emerald-500 shadow-xs cursor-pointer"
              >
                <option value="GN">General (GN)</option>
                <option value="TQ">Tatkal (TQ)</option>
                <option value="PT">Premium Tatkal (PT)</option>
                <option value="LD">Ladies (LD)</option>
                <option value="SS">Senior Citizen (SS)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section: Auto-Fetched Trains & Timings on Route */}
        <div className="glass-panel rounded-2xl p-6 shadow-lg border border-zinc-200/70 dark:border-white/10 space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <Train className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
              <h3 className="font-bold text-sm text-zinc-900 dark:text-white">
                Available Trains & Timings on Route
              </h3>
              {routeTrains.length > 0 && (
                <span className="px-2 py-0.5 text-[11px] font-semibold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 rounded-full">
                  {filteredTrains.length} / {routeTrains.length} trains
                </span>
              )}
            </div>
            {loadingTrains && (
              <div className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-500" />
                <span>Checking live route & seat availability...</span>
              </div>
            )}
          </div>

          {/* Timing & Tatkal Filter Bar */}
          {routeTrains.length > 0 && (
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
              <div className="flex items-center gap-1 text-zinc-400 font-semibold shrink-0 pr-1">
                <Filter className="w-3.5 h-3.5" />
                <span>Filter:</span>
              </div>
              {TIMING_FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setTimingFilter(f.id)}
                  className={`px-3 py-1 rounded-lg font-medium shrink-0 transition-all cursor-pointer text-xs ${
                    timingFilter === f.id
                      ? 'bg-emerald-600 text-white font-bold shadow-xs'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          )}

          {loadingTrains ? (
            <div className="py-8 flex flex-col items-center justify-center text-center space-y-2 text-zinc-400">
              <Loader2 className="w-6 h-6 animate-spin text-emerald-500" />
              <p className="text-xs">Fetching available trains, coaches & fares for {fromStation || '...'} ➔ {toStation || '...'}</p>
            </div>
          ) : filteredTrains.length > 0 ? (
            <div className="space-y-4">
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Click any train to select. Click any coach box to choose class and lock live availability & fare:
              </p>
              <div className="grid grid-cols-1 gap-3.5">
                {filteredTrains.map((tr) => {
                  const isSelected = trainPreference === tr.train_number;
                  return (
                    <div
                      key={tr.train_number}
                      onClick={() => selectTrain(tr)}
                      className={`relative p-4 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'border-emerald-500 bg-emerald-50/30 dark:bg-emerald-950/20 ring-2 ring-emerald-500/20 shadow-xs'
                          : 'border-zinc-200/80 dark:border-zinc-800 bg-zinc-50/60 dark:bg-zinc-800/30 hover:border-zinc-300 dark:hover:border-zinc-700'
                      }`}
                    >
                      {/* Top Row: Train Number, Name, Type */}
                      <div className="flex items-start justify-between gap-2 mb-2.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`px-2 py-0.5 text-xs font-mono font-bold rounded-md ${
                            isSelected 
                              ? 'bg-emerald-600 text-white' 
                              : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-800 dark:text-zinc-200'
                          }`}>
                            {tr.train_number}
                          </span>
                          <span className="font-bold text-xs text-zinc-900 dark:text-white">
                            {tr.train_name}
                          </span>
                          {tr.timing_slot_label && (
                            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-zinc-200/60 dark:bg-zinc-700/50 text-zinc-600 dark:text-zinc-300">
                              {tr.timing_slot_label}
                            </span>
                          )}
                        </div>
                        {isSelected ? (
                          <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 shrink-0">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            Selected
                          </span>
                        ) : (
                          tr.type && (
                            <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 bg-zinc-200/60 dark:bg-zinc-700/60 text-zinc-600 dark:text-zinc-300 rounded shrink-0">
                              {tr.type}
                            </span>
                          )
                        )}
                      </div>

                      {/* Middle Row: Schedule / Timings */}
                      <div className="bg-white dark:bg-zinc-900/80 rounded-lg p-2.5 border border-zinc-200/60 dark:border-zinc-800/80 mb-3">
                        <div className="flex items-center justify-between text-xs">
                          {/* Departure */}
                          <div className="text-left">
                            <div className="font-bold text-sm text-zinc-900 dark:text-white">
                              {tr.departure_time || '--:--'}
                            </div>
                            <div className="text-[11px] font-medium text-zinc-500 dark:text-zinc-400">
                              {tr.from_station} {tr.from_station_name ? `(${tr.from_station_name})` : ''}
                            </div>
                          </div>

                          {/* Duration Badge */}
                          <div className="flex flex-col items-center px-2">
                            <div className="flex items-center gap-1 text-[10px] font-semibold text-zinc-500 dark:text-zinc-400">
                              <Clock className="w-3 h-3 text-emerald-500" />
                              <span>{tr.duration || 'Direct'}</span>
                            </div>
                            <div className="flex items-center gap-1 text-zinc-300 dark:text-zinc-600 my-0.5">
                              <div className="w-8 h-[1.5px] bg-zinc-300 dark:bg-zinc-700" />
                              <ArrowRight className="w-3 h-3 text-zinc-400" />
                            </div>
                            <span className="text-[9px] text-zinc-400">
                              {tr.stops && tr.stops.length > 0 ? `${tr.stops.length} stops` : 'Non-stop'}
                            </span>
                          </div>

                          {/* Arrival */}
                          <div className="text-right">
                            <div className="font-bold text-sm text-zinc-900 dark:text-white">
                              {tr.arrival_time || '--:--'}
                            </div>
                            <div className="text-[11px] font-medium text-zinc-500 dark:text-zinc-400">
                              {tr.to_station} {tr.to_station_name ? `(${tr.to_station_name})` : ''}
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Bottom Row: Coach & Live Seat Availability Grid with Prices */}
                      <div className="space-y-1.5 pt-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-semibold text-zinc-600 dark:text-zinc-400">
                            Coach & Live Seat Availability:
                          </span>
                          {tr.tatkal_ac_open && (
                            <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium flex items-center gap-1">
                              <Zap className="w-2.5 h-2.5" />
                              Tatkal: {tr.tatkal_ac_open} (AC) / {tr.tatkal_nonac_open} (Non-AC)
                            </span>
                          )}
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2">
                          {(tr.coaches && tr.coaches.length > 0
                            ? tr.coaches
                            : (tr.classes || ['3A', '2A', 'SL']).map((cls) => ({
                                class_code: cls,
                                class_name: cls,
                                status: 'AVAILABLE',
                                color: 'emerald',
                                fare: 1080
                              }))
                          ).map((coach) => {
                            const isClassActive = isSelected && journeyClass === coach.class_code;
                            const isAvailable = coach.color === 'emerald';
                            const isRAC = coach.color === 'amber';

                            return (
                              <button
                                key={coach.class_code}
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  selectTrain(tr, coach.class_code);
                                }}
                                className={`p-2 rounded-lg border text-left transition-all cursor-pointer flex flex-col justify-between ${
                                  isClassActive
                                    ? 'border-emerald-500 bg-emerald-50/80 dark:bg-emerald-950/60 ring-2 ring-emerald-500/30 shadow-xs'
                                    : 'border-zinc-200 dark:border-zinc-700/80 bg-white dark:bg-zinc-800/80 hover:border-emerald-400 dark:hover:border-emerald-500'
                                }`}
                              >
                                <div className="flex items-center justify-between gap-1 mb-1">
                                  <span className="font-bold text-xs text-zinc-900 dark:text-white">
                                    {coach.class_code}
                                  </span>
                                  <span className="text-[11px] font-extrabold text-zinc-800 dark:text-zinc-200">
                                    ₹{coach.fare || '--'}
                                  </span>
                                </div>

                                <div className="flex items-center gap-1">
                                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md flex items-center gap-1 w-full justify-center ${
                                    isAvailable
                                      ? 'bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-200'
                                      : isRAC
                                      ? 'bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200'
                                      : 'bg-rose-100 dark:bg-rose-900/60 text-rose-800 dark:text-rose-200'
                                  }`}>
                                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                      isAvailable ? 'bg-emerald-500 animate-pulse' : isRAC ? 'bg-amber-500' : 'bg-rose-500'
                                    }`} />
                                    <span className="truncate">{coach.status || 'AVAILABLE'}</span>
                                  </span>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Live Fare & Selected Coach Summary Breakdown Card */}
              {selectedCoach && selectedTrainObj && (
                <div className="p-4 bg-emerald-50/60 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/80 rounded-xl space-y-2 mt-4 animate-fade-in">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold text-emerald-900 dark:text-emerald-300">
                        Selected: Train {selectedTrainObj.train_number} • Coach {selectedCoach.class_name || selectedCoach.class_code}
                      </span>
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-md ${
                        selectedCoach.color === 'emerald'
                          ? 'bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-200'
                          : selectedCoach.color === 'amber'
                          ? 'bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200'
                          : 'bg-rose-100 dark:bg-rose-900/60 text-rose-800 dark:text-rose-200'
                      }`}>
                        {selectedCoach.status}
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-[11px] text-zinc-500 dark:text-zinc-400">Total Fare: </span>
                      <span className="text-base font-extrabold text-emerald-700 dark:text-emerald-400">
                        ₹{totalEstimatedFare.toLocaleString('en-IN')}
                      </span>
                      <span className="text-[10px] text-zinc-400 ml-1">({passengers.length} passenger{passengers.length > 1 ? 's' : ''})</span>
                    </div>
                  </div>

                  {selectedCoach.fare_breakdown && (
                    <div className="pt-2 border-t border-emerald-200/60 dark:border-emerald-800/60 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-zinc-600 dark:text-zinc-400">
                      <div>Base Fare: <strong className="text-zinc-800 dark:text-zinc-200">₹{selectedCoach.fare_breakdown.base_fare}</strong></div>
                      <div>Reservation Fee: <strong className="text-zinc-800 dark:text-zinc-200">₹{selectedCoach.fare_breakdown.reservation_charge}</strong></div>
                      <div>Superfast Charge: <strong className="text-zinc-800 dark:text-zinc-200">₹{selectedCoach.fare_breakdown.superfast_charge}</strong></div>
                      <div>GST / Tax: <strong className="text-zinc-800 dark:text-zinc-200">₹{selectedCoach.fare_breakdown.service_tax}</strong></div>
                    </div>
                  )}

                  {selectedCoach.tatkal_open_time && (
                    <div className="text-[10px] text-amber-700 dark:text-amber-400 flex items-center gap-1 pt-1 border-t border-emerald-200/40 dark:border-emerald-800/40">
                      <Zap className="w-3 h-3 text-amber-500" />
                      <span>Tatkal Booking Window: <strong>{selectedCoach.tatkal_open_time} (1 day prior to journey)</strong></span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="p-4 bg-zinc-50 dark:bg-zinc-800/40 rounded-xl border border-dashed border-zinc-200 dark:border-zinc-700 text-xs text-zinc-500 dark:text-zinc-400 flex items-center gap-3">
              <Sparkles className="w-4 h-4 text-emerald-500 shrink-0" />
              <div>
                <span>No trains match timing filter <strong className="text-zinc-800 dark:text-zinc-200">"{timingFilter}"</strong>.</span>
                <span className="ml-1">Switch to <strong>All Trains</strong> to see available trains for this route.</span>
              </div>
            </div>
          )}
        </div>


        {/* Section 2: Passengers */}
        <div className="glass-panel rounded-2xl p-6 shadow-lg border border-zinc-200/70 dark:border-white/10 space-y-4">
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
        <div className="glass-panel rounded-2xl p-6 shadow-lg border border-zinc-200/70 dark:border-white/10 space-y-4">
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

          {/* Official Mode Banner */}
          <div className="mt-4 p-4 rounded-xl border border-emerald-500/30 bg-emerald-50/30 dark:bg-emerald-950/20 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold text-emerald-900 dark:text-emerald-300">
                Official IRCTC Automation Active
              </p>
              <p className="text-[11px] text-emerald-700 dark:text-emerald-400 mt-0.5">
                Automates real browser on official irctc.co.in with manual security & payment handoffs.
              </p>
            </div>
            <span className="px-3 py-1 bg-emerald-600 text-white rounded-lg text-xs font-bold shadow-xs">
              Live Official IRCTC
            </span>
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
                  <span className="text-zinc-500 dark:text-zinc-400">Train:</span>
                  <span className="font-bold text-zinc-900 dark:text-white">
                    {trainPreference} {selectedTrainObj?.train_name ? `(${selectedTrainObj.train_name})` : ''}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Route:</span>
                  <span className="font-bold text-zinc-900 dark:text-white">{fromStation} ➔ {toStation}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Date:</span>
                  <span className="font-semibold text-zinc-900 dark:text-white">{journeyDate}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Class & Availability:</span>
                  <span className="font-semibold text-zinc-900 dark:text-white">
                    {journeyClass} {selectedCoach ? `• ${selectedCoach.status}` : ''} | Quota: {quota}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Passengers ({passengers.length}):</span>
                  <span className="font-semibold text-zinc-900 dark:text-white">{passengers.map(p => p.name).join(', ')}</span>
                </div>
                <div className="flex justify-between items-center pt-1 border-t border-zinc-200 dark:border-zinc-700">
                  <span className="text-zinc-500 dark:text-zinc-400">Total Est. Fare:</span>
                  <span className="font-extrabold text-sm text-emerald-600 dark:text-emerald-400">
                    ₹{totalEstimatedFare.toLocaleString('en-IN')}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500 dark:text-zinc-400">Mode:</span>
                  <span className="font-bold text-emerald-600 dark:text-emerald-400">Live Official IRCTC</span>
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
