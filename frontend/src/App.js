import React, { useState, useEffect } from 'react';

function App() {
  const [plexStatus, setPlexStatus] = useState('Disconnected');
  const [plexServerInfo, setPlexServerInfo] = useState(null);
  const [prerolls, setPrerolls] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [categories, setCategories] = useState([]);
  const [holidayPresets, setHolidayPresets] = useState([]);
  const [files, setFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState({});
  const [activeTab, setActiveTab] = useState('dashboard');
  const [plexConfig, setPlexConfig] = useState({
    url: '',
    token: '',
    library: ''
  });
  const [schedulerStatus, setSchedulerStatus] = useState({ running: false, active_schedules: 0 });
  const [backupFile, setBackupFile] = useState(null);
  const [communityTemplates, setCommunityTemplates] = useState([]);
  const [selectedSchedules, setSelectedSchedules] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState(null);
  const [editingPreroll, setEditingPreroll] = useState(null);
  const [editingCategory, setEditingCategory] = useState(null);
  const [stableTokenStatus, setStableTokenStatus] = useState({
    has_stable_token: false,
    config_file_exists: false,
    token_length: 0
  });
  const [manualToken, setManualToken] = useState('');

  // Schedule form state
  const [scheduleForm, setScheduleForm] = useState({
    name: '',
    type: 'monthly',
    start_date: '',
    end_date: '',
    category_id: '',
    shuffle: false,
    playlist: false
  });

  // Upload form state
  const [uploadForm, setUploadForm] = useState({
    tags: '',
    category_id: '',
    description: ''
  });

  // Filter state
  const [filterTags, setFilterTags] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [availableTags, setAvailableTags] = useState([]);

  // Load theme preference from localStorage
  useEffect(() => {
    const savedTheme = localStorage.getItem('darkMode');
    if (savedTheme) {
      setDarkMode(JSON.parse(savedTheme));
    }
  }, []);

  // Save theme preference to localStorage
  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(darkMode));
    document.body.className = darkMode ? 'dark' : 'light';
  }, [darkMode]);

  const toggleTheme = () => {
    setDarkMode(!darkMode);
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchData = () => {
    // Fetch all data
    Promise.all([
      fetch('http://localhost:9393/plex/status'),
      fetch(`http://localhost:9393/prerolls?category_id=${filterCategory}&tags=${filterTags}`),
      fetch('http://localhost:9393/schedules'),
      fetch('http://localhost:9393/categories'),
      fetch('http://localhost:9393/holiday-presets'),
      fetch('http://localhost:9393/scheduler/status'),
      fetch('http://localhost:9393/tags'),
      fetch('http://localhost:9393/community-templates'),
      fetch('http://localhost:9393/plex/stable-token/status')
    ]).then(responses => Promise.all(responses.map(r => r.json())))
      .then(([plex, prerolls, schedules, categories, holidays, scheduler, tags, templates, stableToken]) => {
        setPlexStatus(plex.connected ? 'Connected' : 'Disconnected');
        setPlexServerInfo(plex);
        setPrerolls(Array.isArray(prerolls) ? prerolls : []);
        setSchedules(Array.isArray(schedules) ? schedules : []);
        setCategories(Array.isArray(categories) ? categories : []);
        setHolidayPresets(Array.isArray(holidays) ? holidays : []);
        setSchedulerStatus(scheduler || { running: false, active_schedules: 0 });
        setAvailableTags(Array.isArray(tags?.tags) ? tags.tags : []);
        setCommunityTemplates(Array.isArray(templates) ? templates : []);
        setStableTokenStatus(stableToken || {
          has_stable_token: false,
          config_file_exists: false,
          token_length: 0
        });
      }).catch(err => {
        console.error('Fetch error:', err);
        // Set default values on error
        setPrerolls([]);
        setSchedules([]);
        setCategories([]);
        setHolidayPresets([]);
        setSchedulerStatus({ running: false, active_schedules: 0 });
        setAvailableTags([]);
        setCommunityTemplates([]);
        setStableTokenStatus({
          has_stable_token: false,
          config_file_exists: false,
          token_length: 0
        });
      });
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (files.length === 0) {
      alert('Please select files to upload');
      return;
    }

    const totalFiles = files.length;
    const results = [];

    // Reset progress
    setUploadProgress({});

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append('file', file);
      if (uploadForm.tags.trim()) formData.append('tags', uploadForm.tags.trim());
      if (uploadForm.category_id) formData.append('category_id', uploadForm.category_id);
      if (uploadForm.description.trim()) formData.append('description', uploadForm.description.trim());

      try {
        const formData = new FormData();
        formData.append('file', file);
        if (uploadForm.tags.trim()) formData.append('tags', uploadForm.tags.trim());
        if (uploadForm.category_id) formData.append('category_id', uploadForm.category_id);
        if (uploadForm.description.trim()) formData.append('description', uploadForm.description.trim());

        const response = await fetch('http://localhost:9393/prerolls/upload', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        results.push({ file: file.name, success: true, data });

        // Update progress
        setUploadProgress(prev => ({
          ...prev,
          [file.name]: { status: 'completed', progress: 100 }
        }));

      } catch (error) {
        console.error(`Upload error for ${file.name}:`, error);
        results.push({ file: file.name, success: false, error: error.message });

        // Update progress with error
        setUploadProgress(prev => ({
          ...prev,
          [file.name]: { status: 'error', progress: 0, error: error.message }
        }));
      }
    }

    // Show summary
    const successful = results.filter(r => r.success).length;
    const failed = results.filter(r => !r.success).length;

    if (failed === 0) {
      alert(`All ${totalFiles} files uploaded successfully!`);
    } else if (successful === 0) {
      alert(`Failed to upload any files. Please check the errors.`);
    } else {
      alert(`${successful} files uploaded successfully, ${failed} failed.`);
    }

    // Clear files and form
    setFiles([]);
    setUploadForm({ tags: '', category_id: '', description: '' });
    fetchData();
  };

  const handleCreateSchedule = (e) => {
    e.preventDefault();

    // Validate required fields
    if (!scheduleForm.name.trim()) {
      alert('Schedule name is required');
      return;
    }
    if (!scheduleForm.start_date) {
      alert('Start date is required');
      return;
    }
    if (!scheduleForm.category_id) {
      alert('Please select a category');
      return;
    }

    // Ensure category_id is valid
    const categoryId = parseInt(scheduleForm.category_id);
    if (isNaN(categoryId) || categoryId <= 0) {
      alert('Please select a valid category');
      return;
    }

    const scheduleData = {
      name: scheduleForm.name.trim(),
      type: scheduleForm.type,
      start_date: scheduleForm.start_date,
      end_date: scheduleForm.end_date || null,
      category_id: categoryId,
      shuffle: scheduleForm.shuffle,
      playlist: scheduleForm.playlist
    };

    fetch('http://localhost:9393/schedules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData)
    })
      .then(res => {
        if (!res.ok) {
          return res.text().then(text => {
            throw new Error(`HTTP ${res.status}: ${text}`);
          });
        }
        return res.json();
      })
      .then(data => {
        alert('Schedule created successfully!');
        setScheduleForm({
          name: '', type: 'monthly', start_date: '', end_date: '',
          category_id: '', shuffle: false, playlist: false
        });
        // Add the new schedule to the state immediately with category info
        if (data.category) {
          setSchedules(prev => [...prev, data]);
        } else {
          // If no category in response, refresh data
          fetchData();
        }
      })
      .catch(error => {
        console.error('Schedule creation error:', error);
        alert('Failed to create schedule: ' + error.message);
      });
  };

  const handleInitHolidays = () => {
    fetch('http://localhost:9393/holiday-presets/init', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert('Holiday presets initialized!');
        fetchData();
      });
  };

  const handleApplyCategoryToPlex = (categoryId, categoryName) => {
    const message = `Apply category "${categoryName}" to Plex?\n\nThis will send ALL prerolls from this category to Plex. Plex will automatically rotate through them during playback.`;
    if (window.confirm(message)) {
      fetch(`http://localhost:9393/categories/${categoryId}/apply-to-plex`, { method: 'POST' })
        .then(res => {
          if (!res.ok) {
            return res.json().then(err => {
              throw new Error(err.detail || 'Failed to apply category to Plex');
            });
          }
          return res.json();
        })
        .then(data => {
          let successMessage = `Category applied to Plex!\n\nPrerolls applied (${data.preroll_count} total):`;
          if (data.prerolls && data.prerolls.length > 0) {
            data.prerolls.forEach((preroll, index) => {
              successMessage += `\n${index + 1}. ${preroll}`;
            });
          }
          if (data.rotation_info) {
            successMessage += `\n\n${data.rotation_info}`;
          }
          alert(successMessage);
          fetchData();
        })
        .catch(error => {
          alert('Failed to apply category to Plex: ' + error.message);
        });
    }
  };


  const handleRemoveCategoryFromPlex = (categoryId, categoryName) => {
    if (window.confirm(`Remove category "${categoryName}" from Plex?`)) {
      fetch(`http://localhost:9393/categories/${categoryId}/remove-from-plex`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
          alert('Category removed from Plex!');
          fetchData();
        })
        .catch(error => {
          alert('Failed to remove category from Plex: ' + error.message);
        });
    }
  };

  const toggleScheduler = () => {
    const action = schedulerStatus.running ? 'stop' : 'start';
    fetch(`http://localhost:9393/scheduler/${action}`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert(`Scheduler ${action}ed!`);
        fetchData();
      });
  };

  const handleBackupDatabase = () => {
    fetch('http://localhost:9393/backup/database')
      .then(res => res.json())
      .then(data => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `nexroll_backup_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        alert('Database backup downloaded!');
      })
      .catch(error => {
        console.error('Backup error:', error);
        alert('Backup failed: ' + error.message);
      });
  };

  const handleBackupFiles = () => {
    fetch('http://localhost:9393/backup/files', {
      method: 'POST'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        // Convert base64 or binary data to blob
        const blob = new Blob([new Uint8Array(data.content)], { type: data.content_type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        alert('Files backup downloaded!');
      })
      .catch(error => {
        console.error('File backup error:', error);
        alert('File backup failed: ' + error.message);
      });
  };

  const handleRestoreDatabase = () => {
    if (!backupFile) {
      alert('Please select a backup file first');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const backupData = JSON.parse(e.target.result);
        fetch('http://localhost:9393/restore/database', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(backupData)
        })
          .then(res => res.json())
          .then(data => {
            alert('Database restored successfully!');
            setBackupFile(null);
            fetchData();
          })
          .catch(error => {
            console.error('Restore error:', error);
            alert('Restore failed: ' + error.message);
          });
      } catch (error) {
        alert('Invalid backup file format');
      }
    };
    reader.readAsText(backupFile);
  };

  const handleRestoreFiles = () => {
    if (!backupFile) {
      alert('Please select a ZIP file first');
      return;
    }

    const formData = new FormData();
    formData.append('file', backupFile);
    fetch('http://localhost:9393/restore/files', {
      method: 'POST',
      body: formData
    })
      .then(res => res.json())
      .then(data => {
        alert('Files restored successfully!');
        setBackupFile(null);
      })
      .catch(error => {
        console.error('File restore error:', error);
        alert('File restore failed: ' + error.message);
      });
  };

  const handleInitTemplates = () => {
    fetch('http://localhost:9393/community-templates/init', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert('Community templates initialized!');
        fetchData();
      })
      .catch(error => {
        console.error('Template init error:', error);
        alert('Failed to initialize templates: ' + error.message);
      });
  };

  const handleImportTemplate = (templateId) => {
    fetch(`http://localhost:9393/community-templates/${templateId}/import`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        alert(`Template imported! ${data.imported_schedules} schedules created.`);
        fetchData();
      })
      .catch(error => {
        console.error('Template import error:', error);
        alert('Failed to import template: ' + error.message);
      });
  };

  const handleCreateTemplate = () => {
    if (selectedSchedules.length === 0) {
      alert('Please select at least one schedule to create a template');
      return;
    }

    const templateName = prompt('Enter template name:');
    if (!templateName) return;

    const templateDescription = prompt('Enter template description:');
    const templateCategory = prompt('Enter template category (e.g., Holiday, Seasonal, Custom):', 'Custom');

    const templateData = {
      name: templateName,
      description: templateDescription || '',
      author: 'NeXroll User',
      category: templateCategory || 'Custom',
      schedule_ids: JSON.stringify(selectedSchedules),
      tags: JSON.stringify(['user-created'])
    };

    fetch('http://localhost:9393/community-templates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(templateData)
    })
      .then(res => res.json())
      .then(data => {
        alert('Template created successfully!');
        setSelectedSchedules([]);
        fetchData();
      })
      .catch(error => {
        console.error('Template creation error:', error);
        alert('Failed to create template: ' + error.message);
      });
  };

  const handleDeleteSchedule = (scheduleId) => {
    if (!window.confirm('Are you sure you want to delete this schedule?')) return;

    fetch(`http://localhost:9393/schedules/${scheduleId}`, {
      method: 'DELETE'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Schedule deleted successfully!');
        fetchData();
      })
      .catch(error => {
        console.error('Delete schedule error:', error);
        alert('Failed to delete schedule: ' + error.message);
      });
  };

  const handleEditSchedule = (schedule) => {
    setEditingSchedule(schedule);
    setScheduleForm({
      name: schedule.name,
      type: schedule.type,
      start_date: schedule.start_date ? new Date(schedule.start_date).toISOString().slice(0, 16) : '',
      end_date: schedule.end_date ? new Date(schedule.end_date).toISOString().slice(0, 16) : '',
      category_id: schedule.category_id || '',
      shuffle: schedule.shuffle,
      playlist: schedule.playlist
    });
  };

  const handleUpdateSchedule = (e) => {
    e.preventDefault();
    if (!editingSchedule) return;

    const scheduleData = {
      name: scheduleForm.name.trim(),
      type: scheduleForm.type,
      start_date: scheduleForm.start_date,
      end_date: scheduleForm.end_date || null,
      category_id: parseInt(scheduleForm.category_id),
      shuffle: scheduleForm.shuffle,
      playlist: scheduleForm.playlist
    };

    fetch(`http://localhost:9393/schedules/${editingSchedule.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(scheduleData)
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Schedule updated successfully!');
        setEditingSchedule(null);
        setScheduleForm({
          name: '', type: 'monthly', start_date: '', end_date: '',
          category_id: '', shuffle: false, playlist: false
        });
        fetchData();
      })
      .catch(error => {
        console.error('Update schedule error:', error);
        alert('Failed to update schedule: ' + error.message);
      });
  };

  const handleDeletePreroll = (prerollId) => {
    if (!window.confirm('Are you sure you want to delete this preroll?')) return;

    fetch(`http://localhost:9393/prerolls/${prerollId}`, {
      method: 'DELETE'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Preroll deleted successfully!');
        fetchData();
      })
      .catch(error => {
        console.error('Delete preroll error:', error);
        alert('Failed to delete preroll: ' + error.message);
      });
  };

  const handleEditPreroll = (preroll) => {
    setEditingPreroll(preroll);
    setUploadForm({
      tags: preroll.tags ? (Array.isArray(JSON.parse(preroll.tags)) ? JSON.parse(preroll.tags).join(', ') : preroll.tags) : '',
      category_id: preroll.category_id || '',
      description: preroll.description || ''
    });
  };

  const handleUpdatePreroll = (e) => {
    e.preventDefault();
    if (!editingPreroll) return;

    const updateData = {};
    if (uploadForm.tags.trim()) updateData.tags = uploadForm.tags.trim();
    if (uploadForm.category_id) updateData.category_id = parseInt(uploadForm.category_id);
    if (uploadForm.description.trim()) updateData.description = uploadForm.description.trim();

    fetch(`http://localhost:9393/prerolls/${editingPreroll.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updateData)
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Preroll updated successfully!');
        setEditingPreroll(null);
        setUploadForm({ tags: '', category_id: '', description: '' });
        fetchData();
      })
      .catch(error => {
        console.error('Update preroll error:', error);
        alert('Failed to update preroll: ' + error.message);
      });
  };

  const handleDeleteCategory = (categoryId) => {
    if (!window.confirm('Are you sure you want to delete this category? This may affect associated schedules and prerolls.')) return;

    fetch(`http://localhost:9393/categories/${categoryId}`, {
      method: 'DELETE'
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Category deleted successfully!');
        fetchData();
      })
      .catch(error => {
        console.error('Delete category error:', error);
        alert('Failed to delete category: ' + error.message);
      });
  };

  const handleEditCategory = (category) => {
    setEditingCategory(category);
    setNewCategory({ name: category.name, description: category.description || '' });
  };

  const handleUpdateCategory = (e) => {
    e.preventDefault();
    if (!editingCategory) return;

    fetch(`http://localhost:9393/categories/${editingCategory.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newCategory)
    })
      .then(res => {
        if (!res.ok) {
          throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
      })
      .then(data => {
        alert('Category updated successfully!');
        setEditingCategory(null);
        setNewCategory({ name: '', description: '' });
        fetchData();
      })
      .catch(error => {
        console.error('Update category error:', error);
        alert('Failed to update category: ' + error.message);
      });
  };

  const renderDashboard = () => (
    <div>
      <h1 className="header">NeXroll Dashboard</h1>

      <div className="grid">
        <div className="card">
          <h2>Plex Status</h2>
          <p style={{ color: plexStatus === 'Connected' ? 'green' : 'red' }}>
            {plexStatus}
            {plexServerInfo?.name && (
              <span style={{ fontSize: '0.9rem', marginLeft: '0.5rem' }}>
                - {plexServerInfo.name}
              </span>
            )}
          </p>
          {plexServerInfo && (
            <div style={{ fontSize: '0.8rem', color: '#666', marginTop: '0.5rem' }}>
              <div>Version: {plexServerInfo.version}</div>
              <div>Platform: {plexServerInfo.platform}</div>
            </div>
          )}
        </div>
        <div className="card">
          <h2>Prerolls</h2>
          <p>{prerolls.length} uploaded</p>
        </div>
        <div className="card">
          <h2>Schedules</h2>
          <p>{schedules.length} active</p>
        </div>
        <div className="card">
          <h2>Scheduler</h2>
          <p style={{ color: schedulerStatus.running ? 'green' : 'red' }}>
            {schedulerStatus.running ? 'Running' : 'Stopped'}
          </p>
          <button onClick={toggleScheduler} className="button" style={{ marginTop: '0.5rem' }}>
            {schedulerStatus.running ? 'Stop' : 'Start'} Scheduler
          </button>
        </div>
      </div>

      <div className="upload-section">
        <h2>Upload Prerolls</h2>
        <form onSubmit={handleUpload}>
          <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
            <input
              type="file"
              multiple
              onChange={(e) => setFiles(Array.from(e.target.files))}
              accept="video/*"
              required
            />
            {files.length > 0 && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#666' }}>
                {files.length} file{files.length !== 1 ? 's' : ''} selected
                <ul style={{ marginTop: '0.25rem', paddingLeft: '1rem' }}>
                  {files.map((file, index) => (
                    <li key={index} style={{ fontSize: '0.8rem' }}>
                      {file.name} ({(file.size / (1024 * 1024)).toFixed(1)} MB)
                      {uploadProgress[file.name] && (
                        <span style={{
                          marginLeft: '0.5rem',
                          color: uploadProgress[file.name].status === 'completed' ? 'green' :
                                 uploadProgress[file.name].status === 'error' ? 'red' : '#666'
                        }}>
                          {uploadProgress[file.name].status === 'completed' ? '✓' :
                           uploadProgress[file.name].status === 'error' ? '✗' : '...'}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <input
              type="text"
              placeholder="Tags (comma separated)"
              value={uploadForm.tags}
              onChange={(e) => setUploadForm({...uploadForm, tags: e.target.value})}
              style={{ padding: '0.5rem' }}
            />
            <select
              value={uploadForm.category_id}
              onChange={(e) => setUploadForm({...uploadForm, category_id: e.target.value})}
              style={{ padding: '0.5rem' }}
            >
              <option value="">Select Category (Optional)</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
            <textarea
              placeholder="Description (Optional)"
              value={uploadForm.description}
              onChange={(e) => setUploadForm({...uploadForm, description: e.target.value})}
              rows="3"
              style={{ padding: '0.5rem', resize: 'vertical' }}
            />
          </div>
          <button type="submit" className="button" disabled={files.length === 0}>
            Upload {files.length > 0 ? `${files.length} Preroll${files.length !== 1 ? 's' : ''}` : 'Prerolls'}
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Prerolls</h2>

        {/* Filter Controls */}
        <div style={{ marginBottom: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            style={{ padding: '0.5rem' }}
          >
            <option value="">All Categories</option>
            {categories.map(cat => (
              <option key={cat.id} value={cat.id}>{cat.name}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Filter by tags"
            value={filterTags}
            onChange={(e) => setFilterTags(e.target.value)}
            style={{ padding: '0.5rem' }}
          />
          <button onClick={fetchData} className="button" style={{ padding: '0.5rem 1rem' }}>Filter</button>
        </div>

        {/* Available Tags */}
        {availableTags.length > 0 && (
          <div style={{ marginBottom: '1rem' }}>
            <p style={{ fontSize: '0.9rem', color: '#666' }}>Available tags: {availableTags.join(', ')}</p>
          </div>
        )}

        <div className="preroll-grid">
          {prerolls.map(preroll => (
            <div key={preroll.id} className="preroll-item">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <p style={{ fontWeight: 'bold', margin: 0 }}>{preroll.filename}</p>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    onClick={() => handleEditPreroll(preroll)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem' }}
                    title="Edit preroll"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDeletePreroll(preroll.id)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem', backgroundColor: '#dc3545' }}
                    title="Delete preroll"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              {preroll.thumbnail && <img src={`http://localhost:9393/static/${preroll.thumbnail}`} alt="thumbnail" />}
              {preroll.category && <p style={{ fontSize: '0.8rem', color: '#666' }}>Category: {preroll.category.name}</p>}
              {preroll.tags && (
                <p style={{ fontSize: '0.8rem', color: '#666' }}>
                  Tags: {Array.isArray(preroll.tags) ? preroll.tags.join(', ') : preroll.tags}
                </p>
              )}
              {preroll.description && <p style={{ fontSize: '0.8rem', color: '#666' }}>{preroll.description}</p>}
              {preroll.duration && <p style={{ fontSize: '0.8rem', color: '#666' }}>Duration: {Math.round(preroll.duration)}s</p>}
              <p style={{ fontSize: '0.8rem', color: '#999' }}>
                {new Date(preroll.upload_date).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderSchedules = () => (
    <div>
      <h1 className="header">Schedule Management</h1>

      <div className="upload-section">
        <h2>{editingSchedule ? 'Edit Schedule' : 'Create New Schedule'}</h2>
        <form onSubmit={editingSchedule ? (e) => handleUpdateSchedule(e) : handleCreateSchedule}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
            <input
              type="text"
              placeholder="Schedule Name"
              value={scheduleForm.name}
              onChange={(e) => setScheduleForm({...scheduleForm, name: e.target.value})}
              required
              style={{ padding: '0.5rem' }}
            />
            <select
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
                type="datetime-local"
                value={scheduleForm.end_date}
                onChange={(e) => setScheduleForm({...scheduleForm, end_date: e.target.value})}
                style={{ padding: '0.5rem', width: '100%' }}
              />
            </div>
            <select
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
                      start_date: startDate.toISOString().slice(0, 16),
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
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ marginRight: '1rem' }}>
              <input
                type="checkbox"
                checked={scheduleForm.shuffle}
                onChange={(e) => setScheduleForm({...scheduleForm, shuffle: e.target.checked})}
              />
              Shuffle Prerolls
            </label>
            <label>
              <input
                type="checkbox"
                checked={scheduleForm.playlist}
                onChange={(e) => setScheduleForm({...scheduleForm, playlist: e.target.checked})}
              />
              Use as Playlist
            </label>
          </div>
          <div style={{ marginBottom: '1rem', padding: '1rem', backgroundColor: 'var(--card-bg)', borderRadius: '0.25rem' }}>
            <h3 style={{ marginBottom: '0.5rem', fontSize: '1rem' }}>Fallback Category</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              When no schedule is active, this category will be used as the default for preroll selection.
            </p>
            <select
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
          {editingSchedule && (
            <button
              type="button"
              className="button"
              style={{ marginLeft: '0.5rem', backgroundColor: '#6c757d' }}
              onClick={() => {
                setEditingSchedule(null);
                setScheduleForm({
                  name: '', type: 'monthly', start_date: '', end_date: '',
                  category_id: '', shuffle: false, playlist: false
                });
              }}
            >
              Cancel Edit
            </button>
          )}
        </form>
      </div>

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
                    className="button"
                    style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                  >
                    ✏️ Edit
                  </button>
                  <button
                    onClick={() => handleDeleteSchedule(schedule.id)}
                    className="button"
                    style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem', backgroundColor: '#dc3545' }}
                  >
                    🗑️ Delete
                  </button>
                </div>
              </div>
              <p>Type: {schedule.type} | Category: {schedule.category?.name || 'N/A'}</p>
              <p>Status: {schedule.is_active ? 'Active' : 'Inactive'}</p>
              <p>Shuffle: {schedule.shuffle ? 'Yes' : 'No'} | Playlist: {schedule.playlist ? 'Yes' : 'No'}</p>
              {schedule.last_run && <p>Last Run: {new Date(schedule.last_run).toLocaleString()}</p>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const [newCategory, setNewCategory] = useState({ name: '', description: '' });

  const handleCreateCategory = (e) => {
    e.preventDefault();
    if (!newCategory.name.trim()) {
      alert('Category name is required');
      return;
    }

    fetch('http://localhost:9393/categories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newCategory)
    })
      .then(res => res.json())
      .then(data => {
        alert('Category created successfully!');
        setNewCategory({ name: '', description: '' });
        fetchData();
      })
      .catch(error => {
        console.error('Category creation error:', error);
        alert('Failed to create category: ' + error.message);
      });
  };

  const renderCategories = () => (
    <div>
      <h1 className="header">Category Management</h1>

      <div className="upload-section">
        <h2>{editingCategory ? 'Edit Category' : 'Create New Category'}</h2>
        <form onSubmit={editingCategory ? (e) => handleUpdateCategory(e) : handleCreateCategory}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem', marginBottom: '1rem' }}>
            <input
              type="text"
              placeholder="Category Name"
              value={newCategory.name}
              onChange={(e) => setNewCategory({...newCategory, name: e.target.value})}
              required
              style={{ padding: '0.5rem' }}
            />
            <input
              type="text"
              placeholder="Description (Optional)"
              value={newCategory.description}
              onChange={(e) => setNewCategory({...newCategory, description: e.target.value})}
              style={{ padding: '0.5rem' }}
            />
          </div>
          <button type="submit" className="button">{editingCategory ? 'Update Category' : 'Create Category'}</button>
          {editingCategory && (
            <button
              type="button"
              className="button"
              style={{ marginLeft: '0.5rem', backgroundColor: '#6c757d' }}
              onClick={() => {
                setEditingCategory(null);
                setNewCategory({ name: '', description: '' });
              }}
            >
              Cancel Edit
            </button>
          )}
        </form>
      </div>

      <div className="upload-section">
        <h2>Holiday Presets</h2>
        <button onClick={handleInitHolidays} className="button">Initialize Holiday Presets</button>
        <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
          {holidayPresets.map(preset => (
            <div key={preset.id} style={{ border: '1px solid var(--border-color)', padding: '1rem', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
              <h3>{preset.name}</h3>
              <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                {preset.start_month ?
                  `${preset.start_month}/${preset.start_day} - ${preset.end_month}/${preset.end_day}` :
                  `${preset.month}/${preset.day}`
                }
              </p>
              <p style={{ fontSize: '0.9rem' }}>{preset.description}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Categories</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: '1rem' }}>
          {categories.map(category => (
            <div key={category.id} style={{ border: '1px solid var(--border-color)', padding: '1rem', borderRadius: '0.25rem', backgroundColor: 'var(--card-bg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0 }}>{category.name}</h3>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    onClick={() => handleEditCategory(category)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem' }}
                    title="Edit category"
                  >
                    ✏️
                  </button>
                  <button
                    onClick={() => handleDeleteCategory(category.id)}
                    className="button"
                    style={{ fontSize: '0.7rem', padding: '0.2rem 0.4rem', backgroundColor: '#dc3545' }}
                    title="Delete category"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>{category.description || 'No description'}</p>

              {/* Apply to Plex Section */}
              <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '0.5rem', marginTop: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>Plex Status:</span>
                  <span style={{
                    fontSize: '0.8rem',
                    color: category.apply_to_plex ? 'green' : '#666',
                    fontWeight: category.apply_to_plex ? 'bold' : 'normal'
                  }}>
                    {category.apply_to_plex ? 'Applied' : 'Not Applied'}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    onClick={() => handleApplyCategoryToPlex(category.id, category.name)}
                    className="button"
                    style={{
                      fontSize: '0.7rem',
                      padding: '0.25rem 0.5rem',
                      backgroundColor: category.apply_to_plex ? '#28a745' : '#007bff',
                      flex: 1
                    }}
                    title="Apply this category to Plex"
                  >
                    {category.apply_to_plex ? '🔄 Reapply' : '🎬 Apply to Plex'}
                  </button>
                  {category.apply_to_plex && (
                    <button
                      onClick={() => handleRemoveCategoryFromPlex(category.id, category.name)}
                      className="button"
                      style={{
                        fontSize: '0.7rem',
                        padding: '0.25rem 0.5rem',
                        backgroundColor: '#6c757d'
                      }}
                      title="Remove from Plex"
                    >
                      ❌ Remove
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const handleConnectPlex = (e) => {
    e.preventDefault();
    fetch('http://localhost:9393/plex/connect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: plexConfig.url,
        token: plexConfig.token
      })
    })
      .then(res => res.json())
      .then(data => {
        if (data.connected) {
          alert('Successfully connected to Plex using manual token!');
          fetchData();
        } else {
          alert('Failed to connect to Plex. Please check your URL and token.');
        }
      })
      .catch(error => {
        console.error('Plex connection error:', error);
        alert('Failed to connect to Plex: ' + error.message);
      });
  };

  const handleConnectPlexStableToken = (e) => {
    e.preventDefault();
    fetch('http://localhost:9393/plex/connect/stable-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: plexConfig.url,
        token: '' // Not needed for stable token method
      })
    })
      .then(res => res.json())
      .then(data => {
        if (data.connected) {
          alert('Successfully connected to Plex using stable token!');
          fetchData();
        } else {
          alert('Failed to connect to Plex. Please check your URL and ensure the stable token is configured.');
        }
      })
      .catch(error => {
        console.error('Plex stable token connection error:', error);
        alert('Failed to connect to Plex: ' + error.message);
      });
  };

  const handleDisconnectPlex = () => {
    if (window.confirm('Are you sure you want to disconnect from Plex? This will clear all stored connection settings.')) {
      fetch('http://localhost:9393/plex/disconnect', {
        method: 'POST'
      })
        .then(res => res.json())
        .then(data => {
          alert('Successfully disconnected from Plex!');
          // Clear local state
          setPlexConfig({ url: '', token: '', library: '' });
          setPlexStatus('Disconnected');
          setPlexServerInfo(null);
          fetchData();
        })
        .catch(error => {
          console.error('Plex disconnect error:', error);
          alert('Failed to disconnect from Plex: ' + error.message);
        });
    }
  };

  const renderPlex = () => (
    <div>
      <h1 className="header">Plex Integration</h1>

      <div className="card">
        <h2>Connect to Plex Server</h2>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Connect your local Plex server to enable automatic preroll scheduling and media synchronization.
        </p>

        {/* Manual Token Connection */}
        <div style={{ marginBottom: '2rem', padding: '1rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>Method 1: Manual Token</h3>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Enter your Plex server URL and authentication token manually.
          </p>

          <form onSubmit={handleConnectPlex}>
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  Plex Server URL
                </label>
                <input
                  type="url"
                  placeholder="http://192.168.1.100:32400"
                  value={plexConfig.url}
                  onChange={(e) => setPlexConfig({...plexConfig, url: e.target.value})}
                  required
                  style={{ width: '100%', padding: '0.5rem' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  Plex Token
                </label>
                <input
                  type="password"
                  placeholder="Enter your Plex token"
                  value={plexConfig.token}
                  onChange={(e) => setPlexConfig({...plexConfig, token: e.target.value})}
                  required
                  style={{ width: '100%', padding: '0.5rem' }}
                />
                <p style={{ fontSize: '0.8rem', color: '#666', marginTop: '0.25rem' }}>
                  <strong>How to get your token:</strong><br/>
                  1. Open Plex Web at http://localhost:32400/web<br/>
                  2. Sign in to your Plex account<br/>
                  3. Go to Settings → General → Advanced<br/>
                  4. Enable "Show Advanced" if needed<br/>
                  5. Copy the "Authentication Token"
                </p>
              </div>
            </div>

            <button type="submit" className="button">Connect with Manual Token</button>
          </form>
        </div>

        {/* Stable Token Connection */}
        <div style={{ padding: '1rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem' }}>
          <h3 style={{ marginBottom: '0.5rem', color: 'var(--text-color)' }}>Method 2: Stable Token (Recommended)</h3>
          <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '1rem' }}>
            Use a stable token that doesn't expire. Run the setup script first to configure it.
          </p>

          <div style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'grid', gap: '0.5rem', fontSize: '0.9rem' }}>
              <div><strong>Stable Token Status:</strong>
                <span style={{
                  color: stableTokenStatus.has_stable_token ? 'green' : 'red',
                  marginLeft: '0.5rem'
                }}>
                  {stableTokenStatus.has_stable_token ? 'Configured' : 'Not Configured'}
                </span>
              </div>
              {stableTokenStatus.has_stable_token && (
                <div><strong>Token Length:</strong> {stableTokenStatus.token_length} characters</div>
              )}
            </div>
          </div>

          <form onSubmit={handleConnectPlexStableToken}>
            <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
                  Plex Server URL
                </label>
                <input
                  type="url"
                  placeholder="http://192.168.1.100:32400"
                  value={plexConfig.url}
                  onChange={(e) => setPlexConfig({...plexConfig, url: e.target.value})}
                  required
                  style={{ width: '100%', padding: '0.5rem' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                type="submit"
                className="button"
                disabled={!stableTokenStatus.has_stable_token}
                style={{
                  backgroundColor: stableTokenStatus.has_stable_token ? '#28a745' : '#6c757d',
                  cursor: stableTokenStatus.has_stable_token ? 'pointer' : 'not-allowed'
                }}
              >
                Connect with Stable Token
              </button>
              {!stableTokenStatus.has_stable_token && (
                <span style={{ fontSize: '0.9rem', color: '#666' }}>
                  Run setup script to configure stable token
                </span>
              )}
            </div>
          </form>
        </div>

        {/* Disconnect Button */}
        {plexStatus === 'Connected' && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              onClick={handleDisconnectPlex}
              className="button"
              style={{ backgroundColor: '#dc3545' }}
            >
              Disconnect from Plex
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Plex Status</h2>
        <div style={{ display: 'grid', gap: '0.5rem' }}>
          <div><strong>Connection:</strong> <span style={{ color: plexStatus === 'Connected' ? 'green' : 'red' }}>{plexStatus}</span></div>
          <div><strong>Server URL:</strong> {plexConfig.url || 'Not configured'}</div>
          <div><strong>Token:</strong> {plexConfig.token ? '••••••••' : 'Not configured'}</div>
        </div>
        {plexStatus === 'Connected' && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)' }}>
            <button
              onClick={handleDisconnectPlex}
              className="button"
              style={{ backgroundColor: '#dc3545' }}
            >
              Disconnect from Plex
            </button>
          </div>
        )}
      </div>

      {plexStatus === 'Connected' && (
        <div className="card">
          <h2>Plex Integration Features</h2>
          <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
            With Plex connected, you can:
          </p>
          <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-color)' }}>
            <li>Automatically sync categories and tags from Plex libraries</li>
            <li>Import media from Plex as preroll candidates</li>
            <li>Schedule prerolls to play before specific Plex content</li>
            <li>Monitor Plex server status and connection health</li>
          </ul>
        </div>
      )}
    </div>
  );

  const renderSettings = () => (
    <div>
      <h1 className="header">Settings</h1>

      <div className="card">
        <h2>Theme</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '1rem' }}>
          <span>Current theme: {darkMode ? 'Dark' : 'Light'}</span>
          <button onClick={toggleTheme} className="button">
            Switch to {darkMode ? 'Light' : 'Dark'} Mode
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Backup & Restore</h2>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Create backups of your NeXroll data and restore from previous backups.
        </p>

        <div style={{ display: 'grid', gap: '1rem' }}>
          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>Database Backup</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Export all schedules, categories, and preroll metadata to JSON
            </p>
            <button onClick={handleBackupDatabase} className="button">
              📥 Download Database Backup
            </button>
          </div>

          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>Files Backup</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Export all preroll video files and thumbnails to ZIP
            </p>
            <button onClick={handleBackupFiles} className="button">
              📦 Download Files Backup
            </button>
          </div>

          <div>
            <h3 style={{ marginBottom: '0.5rem' }}>Restore from Backup</h3>
            <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              Select a backup file to restore (JSON for database, ZIP for files)
            </p>
            <input
              type="file"
              onChange={(e) => setBackupFile(e.target.files[0])}
              accept=".json,.zip"
              style={{ marginBottom: '0.5rem' }}
            />
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={handleRestoreDatabase}
                className="button"
                disabled={!backupFile || !backupFile.name.endsWith('.json')}
              >
                🔄 Restore Database
              </button>
              <button
                onClick={handleRestoreFiles}
                className="button"
                disabled={!backupFile || !backupFile.name.endsWith('.zip')}
              >
                📂 Restore Files
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2>Community Templates</h2>
        <p style={{ marginBottom: '1rem', color: 'var(--text-color)' }}>
          Browse and import community-created schedule templates, or create your own to share.
        </p>

        <div style={{ marginBottom: '1rem' }}>
          <button onClick={handleInitTemplates} className="button" style={{ marginRight: '0.5rem' }}>
            🔄 Load Default Templates
          </button>
          <button onClick={handleCreateTemplate} className="button">
            ➕ Create Template from Schedules
          </button>
        </div>

        {/* Schedule Selection for Template Creation */}
        {schedules.length > 0 && (
          <div style={{ marginBottom: '1rem', padding: '1rem', border: '1px solid var(--border-color)', borderRadius: '0.25rem' }}>
            <h3 style={{ marginBottom: '0.5rem' }}>Select Schedules for Template:</h3>
            <div style={{ display: 'grid', gap: '0.5rem' }}>
              {schedules.map(schedule => (
                <label key={schedule.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <input
                    type="checkbox"
                    checked={selectedSchedules.includes(schedule.id)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedSchedules([...selectedSchedules, schedule.id]);
                      } else {
                        setSelectedSchedules(selectedSchedules.filter(id => id !== schedule.id));
                      }
                    }}
                  />
                  <span>{schedule.name} ({schedule.type})</span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Available Templates */}
        <div style={{ display: 'grid', gap: '1rem' }}>
          <h3>Available Templates:</h3>
          {communityTemplates.length === 0 ? (
            <p style={{ color: '#666', fontStyle: 'italic' }}>No templates available. Click "Load Default Templates" to get started.</p>
          ) : (
            communityTemplates.map(template => (
              <div key={template.id} style={{
                border: '1px solid var(--border-color)',
                padding: '1rem',
                borderRadius: '0.25rem',
                backgroundColor: 'var(--card-bg)'
              }}>
                <h4 style={{ marginBottom: '0.5rem' }}>{template.name}</h4>
                <p style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
                  {template.description}
                </p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem', color: '#666' }}>
                  <span>By: {template.author} | Category: {template.category}</span>
                  <span>Downloads: {template.downloads} | Rating: {template.rating}/5</span>
                </div>
                <div style={{ marginTop: '0.5rem' }}>
                  <button
                    onClick={() => handleImportTemplate(template.id)}
                    className="button"
                    style={{ fontSize: '0.8rem', padding: '0.25rem 0.75rem' }}
                  >
                    📥 Import Template
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <h2>System Information</h2>
        <div style={{ display: 'grid', gap: '0.5rem', fontSize: '0.9rem' }}>
          <div><strong>Prerolls:</strong> {prerolls.length}</div>
          <div><strong>Categories:</strong> {categories.length}</div>
          <div><strong>Schedules:</strong> {schedules.length}</div>
          <div><strong>Holiday Presets:</strong> {holidayPresets.length}</div>
          <div><strong>Community Templates:</strong> {communityTemplates.length}</div>
          <div><strong>Scheduler Status:</strong> {schedulerStatus.running ? 'Running' : 'Stopped'}</div>
          <div><strong>Theme:</strong> {darkMode ? 'Dark' : 'Light'}</div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="app-container">
      {/* Header with Logo and Theme Toggle */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1rem',
        padding: '0.5rem 0'
      }}>
        <img
          src={darkMode ? "/NeXroll_Logo_WHT.png" : "/NeXroll_Logo_BLK.png"}
          alt="NeXroll Logo"
          style={{
            maxWidth: '120px',
            height: 'auto'
          }}
        />
        <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
          {darkMode ? '☀️' : '🌙'}
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="tab-buttons">
        <button
          className={`tab-button ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          Dashboard
        </button>
        <button
          className={`tab-button ${activeTab === 'schedules' ? 'active' : ''}`}
          onClick={() => setActiveTab('schedules')}
        >
          Schedules
        </button>
        <button
          className={`tab-button ${activeTab === 'categories' ? 'active' : ''}`}
          onClick={() => setActiveTab('categories')}
        >
          Categories
        </button>
        <button
          className={`tab-button ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          Settings
        </button>
        <button
          className={`tab-button ${activeTab === 'plex' ? 'active' : ''}`}
          onClick={() => setActiveTab('plex')}
        >
          Plex
        </button>
      </div>

      <div className="dashboard">
        {activeTab === 'dashboard' && renderDashboard()}
        {activeTab === 'schedules' && renderSchedules()}
        {activeTab === 'categories' && renderCategories()}
        {activeTab === 'settings' && renderSettings()}
        {activeTab === 'plex' && renderPlex()}
      </div>
    </div>
  );
}

export default App;
