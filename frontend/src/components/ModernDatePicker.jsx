import React, { useState, useEffect, useRef } from 'react';
import { 
  Calendar as CalendarIcon, 
  ChevronLeft, 
  ChevronRight, 
  Sparkles, 
  Zap, 
  Clock, 
  Check, 
  X 
} from 'lucide-react';

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

export default function ModernDatePicker({
  value,
  onChange,
  label = "Journey Date",
  minDate,
  maxDays = 120, // IRCTC 120-day ARP limit
  required = false
}) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // Parse initial date or default to today
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  // Maximum allowed date (120 days from today by default)
  const maxAllowedDate = new Date(today);
  maxAllowedDate.setDate(maxAllowedDate.getDate() + maxDays);

  // Parse current value
  const parsedValue = value ? new Date(value + 'T00:00:00') : today;
  const [viewDate, setViewDate] = useState(new Date(parsedValue));

  useEffect(() => {
    if (value) {
      const d = new Date(value + 'T00:00:00');
      if (!isNaN(d.getTime())) {
        setViewDate(new Date(d));
      }
    }
  }, [value]);

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const formatDateYMD = (date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  const handleSelectDate = (date) => {
    const formatted = formatDateYMD(date);
    onChange(formatted);
    setIsOpen(false);
  };

  const prevMonth = (e) => {
    e.stopPropagation();
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1));
  };

  const nextMonth = (e) => {
    e.stopPropagation();
    setViewDate(new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1));
  };

  // Generate calendar days
  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDayOfMonth = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // Days array
  const calendarCells = [];
  // Empty slots for previous month padding
  for (let i = 0; i < firstDayOfMonth; i++) {
    calendarCells.push(null);
  }
  // Days of current month
  for (let day = 1; day <= daysInMonth; day++) {
    calendarCells.push(new Date(year, month, day));
  }

  // Quick preset shortcuts
  const getPresetDate = (daysAhead) => {
    const d = new Date(today);
    d.setDate(d.getDate() + daysAhead);
    return d;
  };

  const getNextWeekend = () => {
    const d = new Date(today);
    const day = d.getDay();
    const diff = (6 - day + 7) % 7 || 7; // Next Saturday
    d.setDate(d.getDate() + diff);
    return d;
  };

  // Formatting display text
  const selectedDateObj = value ? new Date(value + 'T00:00:00') : today;
  const isSelectedValid = !isNaN(selectedDateObj.getTime());
  
  const formattedDisplay = isSelectedValid ? selectedDateObj.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  }) : 'Select Date';

  const dayOfWeekDisplay = isSelectedValid ? selectedDateObj.toLocaleDateString('en-IN', {
    weekday: 'long'
  }) : '';

  // Days countdown tag
  const diffDays = Math.round((selectedDateObj - today) / (1000 * 60 * 60 * 24));
  let badgeText = '';
  if (diffDays === 0) badgeText = 'Today';
  else if (diffDays === 1) badgeText = 'Tomorrow';
  else if (diffDays > 1) badgeText = `in ${diffDays} days`;
  else if (diffDays < 0) badgeText = 'Past Date';

  return (
    <div ref={containerRef} className={`relative w-full ${isOpen ? 'z-50' : 'z-10'}`}>
      {label && (
        <label className="block text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-1 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <CalendarIcon className="w-3.5 h-3.5 text-emerald-500" />
            {label}
          </span>
          {badgeText && (
            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-full ${
              diffDays === 1 ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400' :
              diffDays === 0 ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400' :
              'bg-zinc-200 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300'
            }`}>
              {badgeText}
            </span>
          )}
        </label>
      )}

      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full h-11 px-3.5 rounded-xl border border-zinc-200 dark:border-zinc-700/80 bg-zinc-50/90 dark:bg-zinc-900/80 hover:border-emerald-500/60 dark:hover:border-emerald-500/50 backdrop-blur-md text-left flex items-center justify-between transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 shadow-xs cursor-pointer group"
      >
        <div className="flex items-center gap-2.5 truncate">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform">
            <CalendarIcon className="w-4 h-4" />
          </div>
          <div className="truncate">
            <span className="text-xs font-bold text-zinc-900 dark:text-white">
              {formattedDisplay}
            </span>
            {dayOfWeekDisplay && (
              <span className="text-[11px] text-zinc-500 dark:text-zinc-400 ml-1.5 font-medium">
                • {dayOfWeekDisplay}
              </span>
            )}
          </div>
        </div>
        <div className="text-[10px] font-mono text-zinc-400 dark:text-zinc-500 px-2 py-0.5 rounded bg-zinc-200/50 dark:bg-zinc-800/60">
          IRCTC 120D
        </div>
      </button>

      {/* Modern Popover Calendar */}
      {isOpen && (
        <div className="absolute top-full left-0 z-50 mt-2 w-80 sm:w-88 p-4 rounded-2xl glass-dropdown border border-zinc-200/80 dark:border-white/10 shadow-2xl backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150">
          {/* Quick preset chips */}
          <div className="mb-3.5 pb-3 border-b border-zinc-200/70 dark:border-zinc-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-500 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-amber-500" />
                Quick Select
              </span>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="p-1 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 rounded-md"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => handleSelectDate(today)}
                className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-zinc-100 hover:bg-emerald-50 text-zinc-700 hover:text-emerald-700 dark:bg-zinc-800 dark:hover:bg-zinc-700/80 dark:text-zinc-200 border border-zinc-200/60 dark:border-zinc-700 transition-colors"
              >
                Today
              </button>
              <button
                type="button"
                onClick={() => handleSelectDate(getPresetDate(1))}
                className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border border-emerald-500/30 transition-colors flex items-center gap-1"
              >
                <Zap className="w-3 h-3 text-amber-500" />
                Tomorrow (Tatkal)
              </button>
              <button
                type="button"
                onClick={() => handleSelectDate(getPresetDate(2))}
                className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-zinc-100 hover:bg-zinc-200/70 text-zinc-700 dark:bg-zinc-800 dark:hover:bg-zinc-700/80 dark:text-zinc-200 border border-zinc-200/60 dark:border-zinc-700 transition-colors"
              >
                +2 Days
              </button>
              <button
                type="button"
                onClick={() => handleSelectDate(getNextWeekend())}
                className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-700 dark:text-indigo-300 border border-indigo-500/30 transition-colors"
              >
                Weekend
              </button>
            </div>
          </div>

          {/* Month & Year Navigation Header */}
          <div className="flex items-center justify-between mb-3 px-1">
            <button
              type="button"
              onClick={prevMonth}
              className="p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-300 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <div className="text-xs font-bold text-zinc-900 dark:text-white">
              {MONTH_NAMES[month]} {year}
            </div>
            <button
              type="button"
              onClick={nextMonth}
              className="p-1.5 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-600 dark:text-zinc-300 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Weekday Row */}
          <div className="grid grid-cols-7 gap-1 text-center mb-1.5">
            {WEEKDAYS.map((w, idx) => (
              <div 
                key={w} 
                className={`text-[10px] font-bold py-1 ${
                  idx === 0 || idx === 6 ? 'text-amber-500 dark:text-amber-400' : 'text-zinc-400 dark:text-zinc-500'
                }`}
              >
                {w}
              </div>
            ))}
          </div>

          {/* Days Grid */}
          <div className="grid grid-cols-7 gap-1">
            {calendarCells.map((cell, idx) => {
              if (!cell) {
                return <div key={`empty-${idx}`} className="h-8" />;
              }

              const isPast = cell < today;
              const isBeyondMax = cell > maxAllowedDate;
              const isDisabled = isPast || isBeyondMax;
              const isSelected = formatDateYMD(cell) === value;
              const isCurrentDay = formatDateYMD(cell) === formatDateYMD(today);

              return (
                <button
                  key={cell.toISOString()}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => handleSelectDate(cell)}
                  className={`h-8 rounded-lg text-xs font-semibold flex items-center justify-center relative transition-all duration-150 ${
                    isDisabled 
                      ? 'text-zinc-300 dark:text-zinc-700 cursor-not-allowed' 
                      : isSelected
                      ? 'bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md shadow-emerald-600/30 scale-105 font-bold'
                      : 'hover:bg-emerald-500/15 dark:hover:bg-emerald-500/20 text-zinc-800 dark:text-zinc-200 cursor-pointer'
                  } ${isCurrentDay && !isSelected ? 'border border-emerald-500/50 text-emerald-600 dark:text-emerald-400' : ''}`}
                >
                  {cell.getDate()}
                  {isCurrentDay && !isSelected && (
                    <span className="absolute bottom-1 w-1 h-1 rounded-full bg-emerald-500" />
                  )}
                </button>
              );
            })}
          </div>

          {/* Footer Info */}
          <div className="mt-3.5 pt-2.5 border-t border-zinc-200/70 dark:border-zinc-800 flex items-center justify-between text-[10px] text-zinc-400">
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3 text-emerald-500" />
              Advance Reservation: 120 Days
            </span>
            <button
              type="button"
              onClick={() => handleSelectDate(today)}
              className="text-emerald-600 dark:text-emerald-400 hover:underline font-semibold"
            >
              Reset Today
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
