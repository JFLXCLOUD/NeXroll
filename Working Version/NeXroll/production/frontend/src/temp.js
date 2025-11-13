 // Removed duplicate renderSchedules function
<div className="card nx-toolbar">
  <div className="toolbar-group">
    <button className="button" onClick={() => setShowCalendar(!showCalendar)}>
      {showCalendar ? 'Hide Calendar' : 'Show Calendar'}
    </button>
  </div>

  <div className="toolbar-group">
    <label className="control-label">View</label>
    <select className="nx-select" value={calendarMode} onChange={(e) => setCalendarMode(e.target.value)}>
      <option value="month">Month</option>
      <option value="year">Year</option>
    </select>
  </div>

  {calendarMode === 'month' && (
    <>
      <div className="toolbar-group">
        <label className="control-label">Month</label>
        <select className="nx-select" value={calendarMonth} onChange={(e) => setCalendarMonth(parseInt(e.target.value, 10))}>
          {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
            <option key={m} value={m}>{new Date(2000, m - 1, 1).toLocaleString(undefined, { month: 'long' })}</option>
          ))}
        </select>
      </div>

      <div className="toolbar-group">
        <label className="control-label">Year</label>
        <input
          className="nx-input"
          type="number"
          value={calendarYear}
          onChange={(e) => setCalendarYear(parseInt(e.target.value, 10) || calendarYear)}
          style={{ width: 110 }}
        />
      </div>

      <div className="toolbar-group">
        <div className="view-toggle">
          <button
            type="button"
            className="view-btn"
            onClick={() => { let m = calendarMonth - 1; let y = calendarYear; if (m < 1) { m = 12; y--; } setCalendarMonth(m); setCalendarYear(y); }}
            title="Previous Month"
          >
            <span className="view-icon">â—€</span>
            Prev
          </button>
          <button
            type="button"
            className="view-btn"
            onClick={() => { let m = calendarMonth + 1; let y = calendarYear; if (m > 12) { m = 1; y++; } setCalendarMonth(m); setCalendarYear(y); }}
            title="Next Month"
          >
            Next
            <span className="view-icon">â–¶</span>
          </button>
        </div>
      </div>
    </>
  )}

  {calendarMode === 'year' && (
    <div className="toolbar-group">
      <label className="control-label">Year</label>
      <input
        className="nx-input"
        type="number"
        value={calendarYear}
        onChange={(e) => setCalendarYear(parseInt(e.target.value, 10) || calendarYear)}
        style={{ width: 110 }}
      />
    </div>
  )}
</div>
<div style={{ display: showCalendar ? 'block' : 'none' }}>
  {calendarMode === 'month' ? (() => {
    const monthIndex = calendarMonth - 1;
    const startOfMonth = new Date(calendarYear, monthIndex, 1);
    const start = new Date(startOfMonth);
    start.setDate(start.getDate() - start.getDay()); // back to Sunday

    const days = [];
    for (let i = 0; i < 42; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      days.push(d);
    }

    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = new Date(ensureUtcIso(iso));
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };

    const scheds = (schedules || []).map(s => ({
      ...s,
      sDay: normalizeDay(s.start_date),
      eDay: normalizeDay(s.end_date) ?? normalizeDay(s.start_date),
      cat: catMap.get(s.category_id) || { name: (s.category?.name || 'Unknown'), color: '#6c757d' }
    }));

    const byDay = new Map(); // dayTime -> Set of cat ids
    days.forEach(d => {
      const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
      byDay.set(t, new Set());
    });

    for (const s of scheds) {
      if (s.sDay == null || s.eDay == null) continue;
      for (const d of days) {
        const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
        if (t >= s.sDay && t <= s.eDay) {
          const set = byDay.get(t);
          if (set) set.add(s.category_id);
        }
      }
    }

    const monthName = startOfMonth.toLocaleString(undefined, { month: 'long', year: 'numeric' });

    return (
      <div className="card" style={{ marginBottom: '1rem' }}>
        <h2 style={{ marginTop: 0 }}>{monthName}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '4px' }}>
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(dow => (
            <div key={dow} style={{ fontWeight: 'bold', textAlign: 'center', padding: '4px 0' }}>{dow}</div>
          ))}
          {days.map((d, idx) => {
            const inMonth = d.getMonth() === monthIndex;
            const t = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
            const cats = Array.from(byDay.get(t) || []);
            return (
              <div key={idx} style={{
                border: '1px solid var(--border-color)',
                backgroundColor: inMonth ? 'var(--card-bg)' : 'rgba(0,0,0,0.03)',
                minHeight: 72,
                padding: '4px',
                borderRadius: '4px',
                position: 'relative',
                overflow: 'hidden'
              }}>
                <div style={{ position: 'absolute', top: 4, right: 6, fontSize: '0.8rem', color: '#666' }}>{d.getDate()}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '18px' }}>
                  {cats.slice(0, 4).map((cid, i) => {
                    const cat = catMap.get(cid) || { name: 'Unknown', color: '#6c757d' };
                    return (
                      <span key={cid + '_' + i} title={cat.name} style={{
                        backgroundColor: cat.color, color: '#fff', borderRadius: '3px',
                        padding: '2px 4px', fontSize: '0.72rem', maxWidth: '100%', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                      }}>
                        {cat.name}
                      </span>
                    );
                  })}
                  {cats.length > 4 && (
                    <span style={{ fontSize: '0.72rem', color: '#666' }}>+{cats.length - 4} more</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {(categories || []).map((c, idx) => (
            <span key={c.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem' }}>
              <span style={{ width: 12, height: 12, backgroundColor: palette[idx % palette.length], display: 'inline-block', borderRadius: 2 }} />
              {c.name}
            </span>
          ))}
        </div>
      </div>
    );
  })() : (() => {
    const palette = ['#f94144','#f3722c','#f8961e','#f9844a','#f9c74f','#90be6d','#43aa8b','#577590','#9b5de5','#f15bb5'];
    const catMap = new Map((categories || []).map((c, idx) => [c.id, { name: c.name, color: palette[idx % palette.length] }]));

    // Count scheduled days per month
    const counts = Array.from({ length: 12 }, (_, m) => ({ month: m, cats: new Map() }));
    const normalizeDay = (iso) => {
      if (!iso) return null;
      const d = new Date(ensureUtcIso(iso));
      return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
    };
    const yearStart = new Date(calendarYear, 0, 1).getTime();
    const yearEnd = new Date(calendarYear, 11, 31).getTime();

    for (const s of (schedules || [])) {
      const sDay = normalizeDay(s.start_date);
      const eDay = normalizeDay(s.end_date) ?? sDay;
      if (sDay == null || eDay == null) continue;

      // intersect with chosen year
      const from = Math.max(sDay, yearStart);
      const to = Math.min(eDay, yearEnd);
      if (from > to) continue;

      const catId = s.category_id;
      for (let t = from; t <= to; t += 86400000) {
        const d = new Date(t);
        const m = d.getMonth();
        const map = counts[m].cats;
        map.set(catId, (map.get(catId) || 0) + 1);
      }
    }

    return (
      <div className="card">
        <h2 style={{ marginTop: 0 }}>{calendarYear}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
          {counts.map((entry) => {
            const monthName = new Date(calendarYear, entry.month, 1).toLocaleString(undefined, { month: 'long' });
            const topCats = Array.from(entry.cats.entries()).sort((a, b) => b[1] - a[1]).slice(0, 3);
            return (
              <div key={entry.month} style={{ border: '1px solid var(--border-color)', borderRadius: 6, padding: 8, background: 'var(--card-bg)' }}>
                <div style={{ fontWeight: 'bold', marginBottom: 6 }}>{monthName}</div>
                {topCats.length === 0 ? (
                  <div style={{ fontSize: '0.85rem', color: '#666' }}>No scheduled days</div>
                ) : (
                  <div style={{ display: 'grid', gap: 4 }}>
                    {topCats.map(([cid, cnt], i) => {
                      const cat = catMap.get(cid) || { name: 'Unknown', color: '#6c757d' };
                      return (
                        <div key={cid} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}>
                          <span style={{ width: 12, height: 12, backgroundColor: cat.color, display: 'inline-block', borderRadius: 2 }} />
                          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat.name}</span>
                          <span style={{ color: '#666' }}>{cnt}d</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  })()}
</div>

      <div className="upload-section">
        <h2>Create New Schedule</h2>
        <form onSubmit={handleCreateSchedule}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <input
              className="nx-input"
              type="text"
              placeholder="Schedule Name"
              value={scheduleForm.name}
              onChange={(e) => setScheduleForm({...scheduleForm, name: e.target.value})}
              required
              style={{ padding: '0.5rem' }}
            />
            <select
              className="nx-select"
              value={scheduleForm.type}
              onChange={(e) => setScheduleForm({...scheduleForm, type: e.target.value})}
              style={{ padding: '0.5rem' }}
            >
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
              <option value="holiday">Holiday</option>
              <option value="custom">Custom</option>
            </select>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Start Date & Time</label>
              <input
                className="nx-input"
                type="datetime-local"
                value={scheduleForm.start_date}
                onChange={(e) => setScheduleForm({...scheduleForm, start_date: e.target.value})}
                required
                style={{ padding: '0.5rem', width: '100%' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>End Date & Time (Optional)</label>
              <input
                className="nx-input"
                type="datetime-local"
                value={scheduleForm.end_date}
                onChange={(e) => setScheduleForm({...scheduleForm, end_date: e.target.value})}
                style={{ padding: '0.5rem', width: '100%' }}
              />
            </div>
            <select
              className="nx-select"
              value={scheduleForm.category_id}
              onChange={(e) => setScheduleForm({...scheduleForm, category_id: e.target.value})}
              required
              style={{ padding: '0.5rem' }}
            >
              <option value="">Select Category</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
            <div>
              <label style={{ display: 'block', marginBottom: '0.25rem', fontSize: '0.9rem' }}>Holiday Preset (Optional)</label>
              <select
                className="nx-select"
                value=""
                onChange={(e) => {
                  const preset = holidayPresets.find(p => p.id === parseInt(e.target.value));
                  if (preset) {
                    const currentYear = new Date().getFullYear();

                    // Use date range fields if available, otherwise fall back to single day
                    let startDate, endDate;
                    if (preset.start_month && preset.start_day && preset.end_month && preset.end_day) {
                      // Use the new date range fields
                      startDate = new Date(currentYear, preset.start_month - 1, preset.start_day, 0, 0, 0);
                      endDate = new Date(currentYear, preset.end_month - 1, preset.end_day, 23, 59, 59);
                    } else {
                      // Fall back to old single day format for backward compatibility
                      startDate = new Date(currentYear, preset.month - 1, preset.day, 12, 0, 0);
                      endDate = new Date(currentYear, preset.month - 1, preset.day, 23, 59, 59);
                    }

                    setScheduleForm({
                      ...scheduleForm,
                      name: `${preset.name} Schedule`,
                      type: 'holiday',
                      start_date: toLocalInputFromDate(startDate),
                      end_date: endDate.toISOString().slice(0, 16),
                      category_id: preset.category_id.toString()
                    });
                  }
                }}
                style={{ padding: '0.5rem', width: '100%' }}
              >
                <option value="">Choose Holiday Preset</option>
                {holidayPresets.map(preset => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name} ({preset.start_month ? `${preset.start_month}/${preset.start_day} - ${preset.end_month}/${preset.end_day}` : `${preset.month}/${preset.day}`})
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="nx-checkrow">
            <label className="nx-check">
              <input
                type="checkbox"
                checked={scheduleForm.shuffle}
                onChange={(e) => setScheduleForm({ ...scheduleForm, shuffle: e.target.checked })}
              />
              <span>Random</span>
            </label>
            <label className="nx-check">
              <input
                type="checkbox"
                checked={scheduleForm.playlist}
                onChange={(e) => setScheduleForm({ ...scheduleForm, playlist: e.target.checked })}
              />
              <span>Sequential</span>
            </label>
          </div>
          <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '0.25rem' }}>
            <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>Fallback Category</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              When no schedule is active, this category will be used as the default for preroll selection.
            </p>
            <select
              className="nx-select"
              value={scheduleForm.fallback_category_id || ''}
              onChange={(e) => setScheduleForm({...scheduleForm, fallback_category_id: e.target.value})}
              style={{ padding: '0.5rem', width: '200px' }}
            >
              <option value="">No Fallback</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
          </div>
          <button type="submit" className="button">{editingSchedule ? 'Update Schedule' : 'Create Schedule'}</button>
          {/* edit handled via modal */}
        </form>
      </div>

      {editingSchedule && (
        <Modal
          title="Edit Schedule"
          onClose={() => {
            setEditingSchedule(null);
            setScheduleForm({
              name: '', type: 'monthly', start_date: '', end_date: '',
              category_id: '', shuffle: false, playlist: false, fallback_category_id: ''
            });
          }}
        >
          <form onSubmit={handleUpdateSchedule}>
            <div className="nx-form-grid">
              <div className="nx-field">
                <label className="nx-label">Name</label>
                <input
                  className="nx-input"
                  type="text"
                  placeholder="Schedule Name"
                  value={scheduleForm.name}
                  onChange={(e) => setScheduleForm({...scheduleForm, name: e.target.value})}
                  required
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">Type</label>
                <select
                  className="nx-select"
                  value={scheduleForm.type}
                  onChange={(e) => setScheduleForm({...scheduleForm, type: e.target.value})}
                >
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                  <option value="holiday">Holiday</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div className="nx-field">
                <label className="nx-label">Start Date & Time</label>
                <input
                  className="nx-input"
                  type="datetime-local"
                  value={scheduleForm.start_date}
                  onChange={(e) => setScheduleForm({...scheduleForm, start_date: e.target.value})}
                  required
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">End Date & Time (Optional)</label>
                <input
                  className="nx-input"
                  type="datetime-local"
                  value={scheduleForm.end_date}
                  onChange={(e) => setScheduleForm({...scheduleForm, end_date: e.target.value})}
                />
              </div>
              <div className="nx-field">
                <label className="nx-label">Category</label>
                <select
                  className="nx-select"
                  value={scheduleForm.category_id}
                  onChange={(e) => setScheduleForm({...scheduleForm, category_id: e.target.value})}
                  required
                >
                  <option value="">Select Category</option>
                  {categories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div className="nx-field">
                <label className="nx-label">Fallback Category</label>
                <select
                  className="nx-select"
                  value={scheduleForm.fallback_category_id || ''}
                  onChange={(e) => setScheduleForm({...scheduleForm, fallback_category_id: e.target.value})}
                >
                  <option value="">No Fallback</option>
                  {categories.map(cat => (
                    <option key={cat.id} value={cat.id}>{cat.name}</option>
                  ))}
                </select>
              </div>
              <div className="nx-field nx-span-2">
                <div className="nx-checkrow">
                  <label className="nx-check">
                    <input
                      type="checkbox"
                      checked={scheduleForm.shuffle}
                      onChange={(e) => setScheduleForm({ ...scheduleForm, shuffle: e.target.checked })}
                    />
                    <span>Random</span>
                  </label>
                  <label className="nx-check">
                    <input
                      type="checkbox"
                      checked={scheduleForm.playlist}
                      onChange={(e) => setScheduleForm({ ...scheduleForm, playlist: e.target.checked })}
                    />
                    <span>Sequential</span>
                  </label>
                </div>
              </div>
            </div>
            <div className="nx-actions">
              <button type="submit" className="button">Update Schedule</button>
              <button
                type="button"
                className="button-secondary"
                onClick={() => {
                  setEditingSchedule(null);
                  setScheduleForm({
                    name: '', type: 'monthly', start_date: '', end_date: '',
                    category_id: '', shuffle: false, playlist: false, fallback_category_id: ''
                  });
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      <div className="card">
        <h2>Active Schedules</h2>
        <div style={{ display: 'grid', gap: '1rem' }}>
          {schedules.map(schedule => (
            <div key={schedule.id} style={{ border: '1px solid var(--border-color)', padding: '1rem', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0 }}>{schedule.name}</h3>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={() => handleEditSchedule(schedule)}
                    className="nx-iconbtn"
                  >
                    âœï¸ Edit
                  </button>
                  <button
                    onClick={() => handleDeleteSchedule(schedule.id)}
                    className="nx-iconbtn nx-iconbtn--danger"
                  >
                    ðŸ—‘ï¸ Delete
                  </button>
                </div>
              </div>
              <p>Type: {schedule.type} | Category: {schedule.category?.name || 'N/A'}</p>
              <p>Status: {schedule.is_active ? 'Active' : 'Inactive'}</p>
              <p>Start: {toLocalDisplay(schedule.start_date)}{schedule.end_date ? ` | End: ${toLocalDisplay(schedule.end_date)}` : ''}</p>
              <p>Shuffle: {schedule.shuffle ? 'Yes' : 'No'} | Playlist: {schedule.playlist ? 'Yes' : 'No'}</p>
              {schedule.next_run && <p>Next Run: {toLocalDisplay(schedule.next_run)}</p>}
              {schedule.last_run && <p>Last Run: {toLocalDisplay(schedule.last_run)}</p>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const [newCategory, setNewCategory] = useState({ name: '', description: '', plex_mode: 'shuffle' });
