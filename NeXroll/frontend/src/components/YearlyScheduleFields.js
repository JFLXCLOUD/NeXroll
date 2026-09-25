import React from 'react';
import './YearlyScheduleFields.css';

const months = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

function MonthDayTime({ label, value, onChange, defaultTime }) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(.*)$/.exec(value || '');
  const month = match ? Number(match[2]) : 1;
  const day = match ? Number(match[3]) : 1;
  const time = match ? match[4].slice(0, 5) : defaultTime;
  const days = new Date(2000, month, 0).getDate();
  const update = (m, d, t) => {
    const safeDay = Math.min(d, new Date(2000, m, 0).getDate());
    onChange(`2000-${String(m).padStart(2, '0')}-${String(safeDay).padStart(2, '0')}T${t || defaultTime}`);
  };
  return <fieldset style={{ border: 0, padding: 0, minWidth: 0 }}>
    <legend>{label}</legend>
    <div className="nx-draft-fields">
      <label><span>Month</span><select aria-label={`${label} month`} value={month} onChange={e => update(Number(e.target.value), day, time)}>
        {months.map((name, i) => <option key={name} value={i + 1}>{name}</option>)}
      </select></label>
      <label><span>Day</span><select aria-label={`${label} day`} value={day} onChange={e => update(month, Number(e.target.value), time)}>
        {Array.from({ length: days }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1}</option>)}
      </select></label>
      <label><span>{label === 'Starts' ? 'First day starts at' : 'Last day ends at'}</span><input aria-label={`${label} time`} type="time" value={time} onChange={e => update(month, day, e.target.value)} /></label>
    </div>
  </fieldset>;
}

export default function YearlyScheduleFields({ value, onChange, timeRange = {}, onTimeChange }) {
  const yearRound = !value.end_date;
  if (value.holiday_name && value.holiday_country) {
    return <p>Follows {value.holiday_name} ({value.holiday_country}) automatically, starting in {value.start_date.slice(0, 4)}. Its holiday link and first year are preserved when you save.</p>;
  }
  return <div className="nx-yearly-fields">
    <label><span>Runs every year</span><select aria-label="Yearly date range" value={yearRound ? 'all' : 'range'} onChange={e => onChange({
      ...value,
      start_date: value.start_date || '2000-01-01T00:00',
      end_date: e.target.value === 'all' ? '' : `${(value.start_date || '2000-01-01').slice(0, 10)}T23:59`
    })}><option value="all">All year</option><option value="range">Selected date range</option></select></label>
    {!yearRound && <>
      <MonthDayTime label="Starts" value={value.start_date} defaultTime="00:00" onChange={start_date => onChange({ ...value, start_date })} />
      <MonthDayTime label="Ends" value={value.end_date} defaultTime="23:59" onChange={end_date => onChange({ ...value, end_date })} />
    </>}
    <p>{yearRound ? 'Runs throughout every year.' : 'Repeats every year, continuously from the first day to the last. An end date earlier in the calendar wraps into the next year. Use the same date for a single day.'}</p>
    {!yearRound && /-02-29T/.test(`${value.start_date} ${value.end_date}`) && <p>February 29 runs only in leap years. Other dates within the range still run every year.</p>}
    {onTimeChange && <details open={Boolean(timeRange.start) || undefined}>
      <summary>Daily time window (optional)</summary>
      <p>Leave blank to run continuously. Set times to run only during those hours each day in the season. An earlier end time continues past midnight.</p>
      <div className="nx-draft-fields">
        <label><span>Daily start time</span><input type="time" value={timeRange.start || ''} onChange={e => onTimeChange({ ...timeRange, start: e.target.value })} /></label>
        <label><span>Daily end time</span><input type="time" value={timeRange.end || ''} onChange={e => onTimeChange({ ...timeRange, end: e.target.value })} /></label>
      </div>
    </details>}
  </div>;
}
