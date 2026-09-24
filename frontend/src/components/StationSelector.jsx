import React, { useState, useEffect, useRef } from 'react';
import { MapPin, Search, X, Loader2, Check } from 'lucide-react';
import { searchStations } from '../services/api';

export default function StationSelector({
  label,
  value,
  onChange,
  placeholder = "Search station or state...",
  required = false
}) {
  const [query, setQuery] = useState(value || '');
  const [displayStation, setDisplayStation] = useState(null);
  const [results, setResults] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  // Sync internal display when external value changes
  useEffect(() => {
    if (value) {
      // If we don't have details, fetch station details
      searchStations(value).then((res) => {
        const matched = (res.stations || []).find((s) => s.code.toUpperCase() === value.toUpperCase());
        if (matched) {
          setDisplayStation(matched);
          setQuery(`${matched.name} (${matched.code})`);
        } else {
          setQuery(value);
        }
      }).catch(() => {
        setQuery(value);
      });
    } else {
      setQuery('');
      setDisplayStation(null);
    }
  }, [value]);

  // Click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
        // Revert query to current selection if user blurred without selecting
        if (displayStation) {
          setQuery(`${displayStation.name} (${displayStation.code})`);
        } else if (value) {
          setQuery(value);
        }
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [displayStation, value]);

  // Debounced search
  useEffect(() => {
    const trimmed = query.trim();
    if (!isOpen || trimmed.length === 0) {
      setResults([]);
      return;
    }

    // If query matches current selected station full text, show initial recommendations
    const cleanQ = trimmed.includes('(') ? trimmed.split('(')[0].trim() : trimmed;

    setLoading(true);
    const timer = setTimeout(() => {
      searchStations(cleanQ)
        .then((res) => {
          setResults(res.stations || []);
          setHighlightedIndex(0);
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 180);

    return () => clearTimeout(timer);
  }, [query, isOpen]);

  const handleSelect = (station) => {
    setDisplayStation(station);
    setQuery(`${station.name} (${station.code})`);
    setIsOpen(false);
    onChange(station.code);
  };

  const handleClear = (e) => {
    e.stopPropagation();
    setQuery('');
    setDisplayStation(null);
    setResults([]);
    onChange('');
    inputRef.current?.focus();
  };

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'Enter') {
        setIsOpen(true);
      }
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev < results.length - 1 ? prev + 1 : prev));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightedIndex >= 0 && highlightedIndex < results.length) {
        handleSelect(results[highlightedIndex]);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
    }
  };

  return (
    <div ref={containerRef} className={`relative w-full ${isOpen ? 'z-50' : 'z-10'}`}>
      {label && (
        <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-emerald-500" />
            {label}
          </span>
          {displayStation && (
            <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
              Code: {displayStation.code}
            </span>
          )}
        </label>
      )}

      {/* Input Field with Glass Styling */}
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-400">
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
          ) : (
            <Search className="w-4 h-4" />
          )}
        </div>

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onFocus={() => {
            setIsOpen(true);
            if (!query) {
              // Load default popular hubs on focus if empty
              searchStations('DELHI').then(res => setResults(res.stations || []));
            }
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          required={required}
          className="w-full pl-9 pr-8 py-2.5 text-xs rounded-xl border border-zinc-200/90 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/70 text-zinc-900 dark:text-white backdrop-blur-md focus:outline-hidden focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 shadow-xs transition-all"
        />

        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Modern Glass Dropdown Menu */}
      {isOpen && (
        <div className="absolute left-0 right-0 top-full mt-1.5 z-50 glass-dropdown rounded-2xl max-h-72 overflow-y-auto animate-fade-in p-1.5 space-y-1">
          {loading && results.length === 0 ? (
            <div className="p-4 text-center text-xs text-zinc-400 flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
              <span>Searching real IRCTC stations & states...</span>
            </div>
          ) : results.length > 0 ? (
            <>
              <div className="px-3 py-1.5 text-[10px] font-bold text-zinc-400 uppercase tracking-wider flex items-center justify-between border-b border-black/5 dark:border-white/5 mb-1">
                <span>Select Railway Station</span>
                <span>{results.length} stations found</span>
              </div>
              {results.map((st, idx) => {
                const isSelected = value && value.toUpperCase() === st.code.toUpperCase();
                const isHighlighted = idx === highlightedIndex;

                return (
                  <div
                    key={st.code}
                    onClick={() => handleSelect(st)}
                    onMouseEnter={() => setHighlightedIndex(idx)}
                    className={`px-3 py-2 rounded-xl text-xs flex items-center justify-between cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-emerald-500/15 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 font-semibold'
                        : isHighlighted
                        ? 'bg-zinc-100/80 dark:bg-white/10 text-zinc-900 dark:text-white'
                        : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100/50 dark:hover:bg-white/5'
                    }`}
                  >
                    <div className="flex flex-col min-w-0 pr-2">
                      <div className="flex items-center gap-2">
                        <span className="font-bold truncate text-zinc-900 dark:text-white">
                          {st.name}
                        </span>
                        {st.hindi && (
                          <span className="text-[11px] text-zinc-400 hidden sm:inline">
                            {st.hindi}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-zinc-500 dark:text-zinc-400 mt-0.5">
                        {st.city && <span>{st.city}</span>}
                        {st.city && st.state && <span>•</span>}
                        {st.state && (
                          <span className="text-emerald-600/90 dark:text-emerald-400/90 font-medium">
                            {st.state}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <span className="px-2 py-0.5 text-xs font-mono font-bold rounded-lg bg-zinc-200/70 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-black/5 dark:border-white/10">
                        {st.code}
                      </span>
                      {isSelected && (
                        <Check className="w-4 h-4 text-emerald-500" />
                      )}
                    </div>
                  </div>
                );
              })}
            </>
          ) : (
            <div className="p-4 text-center text-xs text-zinc-500 dark:text-zinc-400">
              <p className="font-semibold text-zinc-700 dark:text-zinc-300">No stations found for "{query}"</p>
              <p className="text-[11px] text-zinc-400 mt-0.5">Try searching by state name (e.g. Rajasthan, Gujarat, UP) or station code (e.g. JP, NDLS).</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
