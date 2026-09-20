import React, { useState } from 'react';
import { 
  Search, 
  Train, 
  MapPin, 
  Clock, 
  Calendar, 
  ArrowRight, 
  CheckCircle2, 
  AlertCircle, 
  RefreshCw, 
  Copy, 
  Check, 
  Radio, 
  FileText,
  Navigation
} from 'lucide-react';
import { checkPNRStatus, checkLiveTrainStatus, searchTrains } from '../services/api';

export default function PNRLiveTracking({ setTab }) {
  const [activeSubTab, setActiveSubTab] = useState('pnr'); // 'pnr' | 'live' | 'search'

  // PNR State
  const [pnrInput, setPnrInput] = useState('');
  const [pnrResult, setPnrResult] = useState(null);
  const [pnrLoading, setPnrLoading] = useState(false);
  const [pnrError, setPnrError] = useState(null);
  const [copiedPnr, setCopiedPnr] = useState(false);

  // Live Train State
  const [trainInput, setTrainInput] = useState('');
  const [trainResult, setTrainResult] = useState(null);
  const [trainLoading, setTrainLoading] = useState(false);
  const [trainError, setTrainError] = useState(null);

  // Search Trains State
  const [fromStation, setFromStation] = useState('NDLS');
  const [toStation, setToStation] = useState('MMCT');
  const [searchResult, setSearchResult] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);

  // Handle PNR Search
  const handlePnrSearch = async (e, customPnr = null) => {
    if (e) e.preventDefault();
    const query = (customPnr || pnrInput).trim();
    if (!query || query.length !== 10) {
      setPnrError('Please enter a valid 10-digit Indian Railways PNR number.');
      return;
    }
    setPnrLoading(true);
    setPnrError(null);
    try {
      const res = await checkPNRStatus(query);
      setPnrResult(res);
    } catch (err) {
      setPnrError(err.message || 'Failed to fetch PNR status.');
    } finally {
      setPnrLoading(false);
    }
  };

  // Handle Live Train Search
  const handleTrainSearch = async (e, customTrain = null) => {
    if (e) e.preventDefault();
    const query = (customTrain || trainInput).trim();
    if (!query) {
      setTrainError('Please enter a 5-digit Train number.');
      return;
    }
    setTrainLoading(true);
    setTrainError(null);
    try {
      const res = await checkLiveTrainStatus(query);
      setTrainResult(res);
    } catch (err) {
      setTrainError(err.message || 'Failed to fetch live train status.');
    } finally {
      setTrainLoading(false);
    }
  };

  // Handle Trains Route Search
  const handleRouteSearch = async (e, customFrom = null, customTo = null) => {
    if (e) e.preventDefault();
    const fromCode = (customFrom || fromStation).trim();
    const toCode = (customTo || toStation).trim();
    if (!fromCode || !toCode) {
      setSearchError('Please provide both Origin and Destination station codes.');
      return;
    }
    setSearchLoading(true);
    setSearchError(null);
    try {
      const res = await searchTrains(fromCode, toCode);
      setSearchResult(res);
    } catch (err) {
      setSearchError(err.message || 'Failed to search trains.');
    } finally {
      setSearchLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedPnr(true);
    setTimeout(() => setCopiedPnr(false), 2000);
  };

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-900 dark:text-white flex items-center gap-2.5">
            <Radio className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
            Live Railway Enquiry & Tracking
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Real-time PNR Status, Train Live Running Location, and Station Route Schedules
          </p>
        </div>

        {/* Sub-Tabs Selector */}
        <div className="bg-zinc-100 dark:bg-zinc-900 p-1 rounded-xl flex items-center gap-1 border border-zinc-200 dark:border-zinc-800 text-xs">
          <button
            onClick={() => setActiveSubTab('pnr')}
            className={`px-3.5 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeSubTab === 'pnr'
                ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white shadow-xs'
                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <Search className="w-3.5 h-3.5 text-blue-500" />
            PNR Status
          </button>
          <button
            onClick={() => setActiveSubTab('live')}
            className={`px-3.5 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeSubTab === 'live'
                ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white shadow-xs'
                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <Navigation className="w-3.5 h-3.5 text-emerald-500" />
            Live Train Status
          </button>
          <button
            onClick={() => setActiveSubTab('search')}
            className={`px-3.5 py-1.5 rounded-lg font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${
              activeSubTab === 'search'
                ? 'bg-white dark:bg-zinc-800 text-zinc-900 dark:text-white shadow-xs'
                : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            <Train className="w-3.5 h-3.5 text-amber-500" />
            Train Search
          </button>
        </div>
      </div>

      {/* ======================= TAB 1: PNR STATUS ======================= */}
      {activeSubTab === 'pnr' && (
        <div className="space-y-6">
          {/* PNR Search Card */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs">
            <form onSubmit={(e) => handlePnrSearch(e)} className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3.5 top-3 w-4 h-4 text-zinc-400" />
                <input
                  type="text"
                  maxLength="10"
                  value={pnrInput}
                  onChange={(e) => setPnrInput(e.target.value.replace(/\D/g, ''))}
                  placeholder="Enter 10-digit PNR Number (e.g. 2451234567)"
                  className="w-full pl-10 pr-4 py-2.5 bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
              <button
                type="submit"
                disabled={pnrLoading}
                className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-md shadow-emerald-600/20 flex items-center justify-center gap-2 cursor-pointer transition-colors"
              >
                {pnrLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" /> Fetching...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" /> Check PNR Status
                  </>
                )}
              </button>
            </form>

            {/* Quick Demo PNRs */}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span className="font-medium">Quick Try:</span>
              {['2451234567', '2898765432', '4123567890'].map((pnr) => (
                <button
                  key={pnr}
                  type="button"
                  onClick={() => {
                    setPnrInput(pnr);
                    handlePnrSearch(null, pnr);
                  }}
                  className="font-mono bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 px-2 py-0.5 rounded text-[11px] text-zinc-700 dark:text-zinc-300 transition-colors cursor-pointer"
                >
                  {pnr}
                </button>
              ))}
            </div>

            {pnrError && (
              <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 rounded-xl text-xs text-rose-700 dark:text-rose-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{pnrError}</span>
              </div>
            )}
          </div>

          {/* PNR Results Card */}
          {pnrResult && (
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-xs animate-fade-in">
              {/* Card Banner */}
              <div className="bg-[#0B3C68] text-white p-5 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
                    <Train className="w-5 h-5 text-[#F37021]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs uppercase tracking-wider text-white/70">PNR Number</span>
                      <button
                        onClick={() => copyToClipboard(pnrResult.pnr)}
                        className="p-1 hover:bg-white/20 rounded transition-colors cursor-pointer"
                        title="Copy PNR"
                      >
                        {copiedPnr ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5 text-white/80" />}
                      </button>
                    </div>
                    <p className="text-xl font-bold font-mono tracking-wider">{pnrResult.pnr}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    pnrResult.chart_prepared 
                      ? 'bg-emerald-500 text-white' 
                      : 'bg-amber-500/30 text-amber-200 border border-amber-400/40'
                  }`}>
                    {pnrResult.chart_prepared ? '✅ Chart Prepared' : '⏳ Chart Not Prepared'}
                  </span>
                  <button
                    onClick={() => {
                      setTrainInput(pnrResult.train_number);
                      setActiveSubTab('live');
                      handleTrainSearch(null, pnrResult.train_number);
                    }}
                    className="px-3 py-1 bg-[#F37021] hover:bg-[#E05E10] text-white text-xs font-semibold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors cursor-pointer"
                  >
                    <Navigation className="w-3 h-3" /> Track Live
                  </button>
                </div>
              </div>

              {/* Train & Journey Information Grid */}
              <div className="p-6 grid grid-cols-1 md:grid-cols-4 gap-4 border-b border-zinc-200 dark:border-zinc-800 text-xs">
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 font-medium">Train</span>
                  <p className="font-bold text-sm text-zinc-900 dark:text-white mt-1">
                    {pnrResult.train_number} - {pnrResult.train_name}
                  </p>
                </div>
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 font-medium">Route</span>
                  <p className="font-bold text-sm text-zinc-900 dark:text-white mt-1 flex items-center gap-1.5">
                    {pnrResult.from_station_name} ({pnrResult.from_station}) 
                    <ArrowRight className="w-3.5 h-3.5 text-zinc-400" /> 
                    {pnrResult.to_station_name} ({pnrResult.to_station})
                  </p>
                </div>
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 font-medium">Journey Date & Class</span>
                  <p className="font-bold text-sm text-zinc-900 dark:text-white mt-1">
                    {pnrResult.journey_date} ({pnrResult.journey_class})
                  </p>
                </div>
                <div>
                  <span className="text-zinc-500 dark:text-zinc-400 font-medium">Timings & Duration</span>
                  <p className="font-bold text-sm text-zinc-900 dark:text-white mt-1">
                    Dep: {pnrResult.departure_time} ➔ Arr: {pnrResult.arrival_time} ({pnrResult.duration})
                  </p>
                </div>
              </div>

              {/* Passenger Status Table */}
              <div className="p-6">
                <h3 className="font-bold text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-3">
                  Passenger Booking & Current Status
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-800/40 text-zinc-500 dark:text-zinc-400">
                        <th className="py-2.5 px-4 font-semibold">#</th>
                        <th className="py-2.5 px-4 font-semibold">Booking Status</th>
                        <th className="py-2.5 px-4 font-semibold">Current Status</th>
                        <th className="py-2.5 px-4 font-semibold">Coach</th>
                        <th className="py-2.5 px-4 font-semibold">Berth</th>
                        <th className="py-2.5 px-4 font-semibold">Berth Type</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
                      {pnrResult.passengers?.map((p, idx) => (
                        <tr key={idx} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
                          <td className="py-3 px-4 font-bold text-zinc-400">Passenger {p.passenger_number}</td>
                          <td className="py-3 px-4 font-medium text-zinc-700 dark:text-zinc-300">{p.booking_status}</td>
                          <td className="py-3 px-4">
                            <span className="px-2 py-0.5 bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 font-bold rounded-md">
                              {p.current_status}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-bold text-zinc-900 dark:text-white">{p.coach}</td>
                          <td className="py-3 px-4 font-bold text-zinc-900 dark:text-white">{p.berth}</td>
                          <td className="py-3 px-4 text-zinc-500">{p.berth_type}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ======================= TAB 2: LIVE TRAIN STATUS ======================= */}
      {activeSubTab === 'live' && (
        <div className="space-y-6">
          {/* Train Input Card */}
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs">
            <form onSubmit={(e) => handleTrainSearch(e)} className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Train className="absolute left-3.5 top-3 w-4 h-4 text-zinc-400" />
                <input
                  type="text"
                  maxLength="5"
                  value={trainInput}
                  onChange={(e) => setTrainInput(e.target.value.replace(/\D/g, ''))}
                  placeholder="Enter 5-digit Train Number (e.g. 12952, 22436, 12301)"
                  className="w-full pl-10 pr-4 py-2.5 bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>
              <button
                type="submit"
                disabled={trainLoading}
                className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-md shadow-emerald-600/20 flex items-center justify-center gap-2 cursor-pointer transition-colors"
              >
                {trainLoading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" /> Locating...
                  </>
                ) : (
                  <>
                    <Navigation className="w-4 h-4" /> Track Live Train
                  </>
                )}
              </button>
            </form>

            {/* Quick Train Tags */}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span className="font-medium">Popular Express:</span>
              {[
                { no: '12952', name: 'Mumbai Rajdhani' },
                { no: '22436', name: 'Vande Bharat (Varanasi)' },
                { no: '12301', name: 'Howrah Rajdhani' },
                { no: '12004', name: 'Lucknow Shatabdi' },
                { no: '12628', name: 'Karnataka Express' }
              ].map((t) => (
                <button
                  key={t.no}
                  type="button"
                  onClick={() => {
                    setTrainInput(t.no);
                    handleTrainSearch(null, t.no);
                  }}
                  className="bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 px-2 py-0.5 rounded text-[11px] text-zinc-700 dark:text-zinc-300 transition-colors cursor-pointer"
                >
                  <b>{t.no}</b> ({t.name})
                </button>
              ))}
            </div>

            {trainError && (
              <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 rounded-xl text-xs text-rose-700 dark:text-rose-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{trainError}</span>
              </div>
            )}
          </div>

          {/* Live Train Result Card */}
          {trainResult && (
            <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl overflow-hidden shadow-xs animate-fade-in">
              {/* Header */}
              <div className="p-6 border-b border-zinc-200 dark:border-zinc-800 flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xl font-bold text-zinc-900 dark:text-white">
                      {trainResult.train_number} - {trainResult.train_name}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500 mt-1 flex items-center gap-1.5">
                    <span>{trainResult.source}</span>
                    <ArrowRight className="w-3.5 h-3.5 text-zinc-400" />
                    <span>{trainResult.destination}</span>
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  <span className={`px-3 py-1.5 rounded-full text-xs font-bold flex items-center gap-1.5 ${
                    trainResult.is_on_time
                      ? 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800'
                      : 'bg-amber-100 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 border border-amber-300 dark:border-amber-800'
                  }`}>
                    <span className="w-2 h-2 rounded-full bg-current animate-pulse"></span>
                    {trainResult.is_on_time ? 'Right Time (On Schedule)' : `Delayed by ${trainResult.delay_minutes} mins`}
                  </span>

                  <span className="text-[11px] text-zinc-400">
                    Updated: {trainResult.last_updated_time}
                  </span>
                </div>
              </div>

              {/* Status 3-box indicator */}
              <div className="p-6 grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-700/80">
                  <span className="text-[11px] uppercase tracking-wider text-zinc-400 font-semibold">Current Location</span>
                  <p className="text-base font-bold text-zinc-900 dark:text-white mt-1">
                    {trainResult.current_station_name} ({trainResult.current_station_code})
                  </p>
                  <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium mt-0.5">
                    Status: {trainResult.status}
                  </p>
                </div>

                <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-700/80">
                  <span className="text-[11px] uppercase tracking-wider text-zinc-400 font-semibold">Next Upcoming Stop</span>
                  <p className="text-base font-bold text-zinc-900 dark:text-white mt-1">
                    {trainResult.next_station_name} ({trainResult.next_station_code})
                  </p>
                  <p className="text-xs text-zinc-500 mt-0.5">En route</p>
                </div>

                <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-xl border border-zinc-200/80 dark:border-zinc-700/80">
                  <span className="text-[11px] uppercase tracking-wider text-zinc-400 font-semibold">Final Destination ETA</span>
                  <p className="text-base font-bold text-zinc-900 dark:text-white mt-1">
                    {trainResult.destination}
                  </p>
                  <p className="text-xs text-blue-600 dark:text-blue-400 font-medium mt-0.5">
                    Expected Arrival: {trainResult.eta_destination} hrs
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ======================= TAB 3: TRAIN ROUTE SEARCH ======================= */}
      {activeSubTab === 'search' && (
        <div className="space-y-6">
          <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-xs">
            <form onSubmit={(e) => handleRouteSearch(e)} className="grid grid-cols-1 sm:grid-cols-5 gap-3">
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-zinc-600 dark:text-zinc-400 mb-1">From Station Code</label>
                <input
                  type="text"
                  value={fromStation}
                  onChange={(e) => setFromStation(e.target.value.toUpperCase())}
                  placeholder="e.g. NDLS"
                  className="w-full px-3.5 py-2.5 bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-zinc-600 dark:text-zinc-400 mb-1">To Station Code</label>
                <input
                  type="text"
                  value={toStation}
                  onChange={(e) => setToStation(e.target.value.toUpperCase())}
                  placeholder="e.g. MMCT"
                  className="w-full px-3.5 py-2.5 bg-zinc-50 dark:bg-zinc-800/60 border border-zinc-200 dark:border-zinc-700 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={searchLoading}
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-md shadow-emerald-600/20 flex items-center justify-center gap-2 cursor-pointer transition-colors"
                >
                  {searchLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  Find Trains
                </button>
              </div>
            </form>

            {/* Quick Popular Routes */}
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
              <span className="font-medium">Top Routes:</span>
              {[
                { f: 'NDLS', t: 'MMCT', label: 'Delhi ➔ Mumbai' },
                { f: 'NDLS', t: 'BSB', label: 'Delhi ➔ Varanasi' },
                { f: 'HWH', t: 'NDLS', label: 'Kolkata ➔ Delhi' },
                { f: 'SBC', t: 'NDLS', label: 'Bengaluru ➔ Delhi' },
              ].map((r) => (
                <button
                  key={r.label}
                  type="button"
                  onClick={() => {
                    setFromStation(r.f);
                    setToStation(r.t);
                    handleRouteSearch(null, r.f, r.t);
                  }}
                  className="bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 px-2 py-0.5 rounded text-[11px] text-zinc-700 dark:text-zinc-300 transition-colors cursor-pointer"
                >
                  {r.label}
                </button>
              ))}
            </div>

            {searchError && (
              <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 rounded-xl text-xs text-rose-700 dark:text-rose-400 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{searchError}</span>
              </div>
            )}
          </div>

          {/* Results List */}
          {searchResult && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-zinc-500 px-1">
                <span>Found <b>{searchResult.count}</b> trains between <b>{searchResult.from_station}</b> and <b>{searchResult.to_station}</b></span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {searchResult.trains?.map((t) => (
                  <div key={t.train_number} className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-5 shadow-xs flex flex-col justify-between gap-4">
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-sm text-zinc-900 dark:text-white">
                          {t.train_number} - {t.train_name}
                        </span>
                        <span className="font-mono text-xs bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded text-zinc-600 dark:text-zinc-300">
                          {t.duration}
                        </span>
                      </div>

                      <div className="mt-3 flex items-center justify-between text-xs">
                        <div>
                          <p className="font-bold text-base text-zinc-900 dark:text-white">{t.departure_time}</p>
                          <p className="text-zinc-400 text-[11px]">{t.from_station_name} ({t.from_station})</p>
                        </div>
                        <ArrowRight className="w-4 h-4 text-zinc-300 dark:text-zinc-600" />
                        <div className="text-right">
                          <p className="font-bold text-base text-zinc-900 dark:text-white">{t.arrival_time}</p>
                          <p className="text-zinc-400 text-[11px]">{t.to_station_name} ({t.to_station})</p>
                        </div>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-1.5">
                        {t.classes?.map((c) => (
                          <span key={c} className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 text-emerald-700 dark:text-emerald-300 text-[11px] font-semibold rounded-md">
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 pt-2 border-t border-zinc-100 dark:border-zinc-800">
                      <button
                        onClick={() => {
                          setTrainInput(t.train_number);
                          setActiveSubTab('live');
                          handleTrainSearch(null, t.train_number);
                        }}
                        className="flex-1 py-1.5 bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-200 text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                      >
                        <Navigation className="w-3.5 h-3.5" /> Track Live
                      </button>
                      <button
                        onClick={() => setTab('new-booking')}
                        className="flex-1 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                      >
                        <Train className="w-3.5 h-3.5" /> Book Now
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
