import React, { useState } from 'react';
import SequenceBuilder from './components/SequenceBuilder';

/**
 * TestSequenceBuilder - Standalone test page for Sequence Builder
 * Access at: http://localhost:3000/test-sequence
 * 
 * To use:
 * 1. Add to App.js: import TestSequenceBuilder from './TestSequenceBuilder';
 * 2. Add route: {window.location.pathname === '/test-sequence' && <TestSequenceBuilder />}
 * 3. Navigate to /test-sequence
 */
function TestSequenceBuilder() {
  const [sequence, setSequence] = useState([
    // Start with a sample sequence for testing
    {
      id: 'block-1',
      type: 'random',
      category_id: 1,
      count: 2
    },
    {
      id: 'block-2',
      type: 'fixed',
      preroll_ids: [4, 5]
    }
  ]);

  // Mock data for testing - mirrors real backend structure
  const mockCategories = [
    { id: 1, name: 'Trivia', description: 'Movie trivia slides' },
    { id: 2, name: 'Coming Soon', description: 'Upcoming movie trailers' },
    { id: 3, name: 'Studio Logos', description: 'Studio intro videos' },
    { id: 4, name: 'Holiday', description: 'Holiday themed prerolls' },
    { id: 5, name: 'Countdown', description: 'Feature presentation countdown' },
  ];

  const mockPrerolls = [
    { id: 1, filename: 'trivia_001.mp4', display_name: 'Movie Trivia: Famous Quotes', category_id: 1, duration: 30 },
    { id: 2, filename: 'trivia_002.mp4', display_name: 'Movie Trivia: Behind the Scenes', category_id: 1, duration: 25 },
    { id: 3, filename: 'trivia_003.mp4', display_name: 'Movie Trivia: Fun Facts', category_id: 1, duration: 28 },
    { id: 4, filename: 'trailer_001.mp4', display_name: 'Coming Soon: Action Movie', category_id: 2, duration: 120 },
    { id: 5, filename: 'trailer_002.mp4', display_name: 'Coming Soon: Comedy Film', category_id: 2, duration: 110 },
    { id: 6, filename: 'disney_intro.mp4', display_name: 'Disney Intro', category_id: 3, duration: 15 },
    { id: 7, filename: 'warner_bros.mp4', display_name: 'Warner Bros Logo', category_id: 3, duration: 10 },
    { id: 8, filename: 'universal.mp4', display_name: 'Universal Studios', category_id: 3, duration: 12 },
    { id: 9, filename: 'christmas_intro.mp4', display_name: 'Christmas Intro', category_id: 4, duration: 20 },
    { id: 10, filename: 'halloween.mp4', display_name: 'Halloween Special', category_id: 4, duration: 25 },
    { id: 11, filename: 'countdown_10.mp4', display_name: '10 Second Countdown', category_id: 5, duration: 10 },
    { id: 12, filename: 'feature_presentation.mp4', display_name: 'Feature Presentation Intro', category_id: 5, duration: 8 },
  ];

  const handleSave = (newSequence) => {
    console.log('✅ Sequence saved!');
    console.log('Raw sequence:', newSequence);
    console.log('JSON output:', JSON.stringify(newSequence, null, 2));
    setSequence(newSequence);
    alert('Sequence saved successfully!\n\nCheck console for details.');
  };

  const handleCancel = () => {
    console.log('❌ Cancelled');
    const confirmed = window.confirm('Cancel sequence editing?');
    if (confirmed) {
      alert('Sequence editing cancelled');
    }
  };

  const handleReset = () => {
    if (window.confirm('Reset to empty sequence?')) {
      setSequence([]);
    }
  };

  const handleLoadSample = () => {
    const sampleSequence = [
      {
        id: 'block-sample-1',
        type: 'random',
        category_id: 1,
        count: 2
      },
      {
        id: 'block-sample-2',
        type: 'fixed',
        preroll_ids: [6, 7]
      },
      {
        id: 'block-sample-3',
        type: 'random',
        category_id: 2,
        count: 1
      },
      {
        id: 'block-sample-4',
        type: 'fixed',
        preroll_ids: [11, 12]
      }
    ];
    setSequence(sampleSequence);
    alert('Sample sequence loaded!\n\n2 random trivia → Disney/Warner logos → 1 random trailer → Countdown');
  };

  return (
    <div style={{ 
      padding: '20px', 
      backgroundColor: '#1a1a2e', 
      minHeight: '100vh',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ 
          marginBottom: '30px', 
          padding: '20px',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: '12px',
          boxShadow: '0 8px 24px rgba(102, 126, 234, 0.3)'
        }}>
          <h1 style={{ 
            color: 'white', 
            margin: '0 0 10px 0',
            fontSize: '32px',
            display: 'flex',
            alignItems: 'center',
            gap: '10px'
          }}>
            🎬 Sequence Builder Test Page
          </h1>
          <p style={{ color: 'rgba(255,255,255,0.9)', margin: 0, fontSize: '16px' }}>
            Test the new Kodi Pre-Show Experience inspired sequence builder
          </p>
        </div>

        {/* Info Panel */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: '1fr 1fr', 
          gap: '20px',
          marginBottom: '30px'
        }}>
          {/* Current Sequence Display */}
          <div style={{ 
            padding: '20px', 
            backgroundColor: 'rgba(0,0,0,0.3)', 
            borderRadius: '8px',
            border: '2px solid #4a5568'
          }}>
            <h2 style={{ 
              color: '#00d4ff', 
              fontSize: '18px', 
              marginTop: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              📊 Current Sequence JSON
            </h2>
            <pre style={{ 
              color: '#0f0', 
              fontSize: '12px', 
              overflow: 'auto',
              backgroundColor: '#000',
              padding: '15px',
              borderRadius: '6px',
              maxHeight: '300px',
              margin: 0
            }}>
              {sequence.length === 0 
                ? '// Empty sequence - add blocks to see JSON'
                : JSON.stringify(sequence, null, 2)}
            </pre>
          </div>

          {/* Test Controls */}
          <div style={{ 
            padding: '20px', 
            backgroundColor: 'rgba(0,0,0,0.3)', 
            borderRadius: '8px',
            border: '2px solid #4a5568'
          }}>
            <h2 style={{ 
              color: '#00d4ff', 
              fontSize: '18px', 
              marginTop: 0,
              marginBottom: '15px'
            }}>
              🧪 Test Controls
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button
                onClick={handleLoadSample}
                style={{
                  padding: '12px 20px',
                  backgroundColor: '#48bb78',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  transition: 'all 0.3s'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#38a169'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#48bb78'}
              >
                📥 Load Sample Sequence
              </button>
              <button
                onClick={handleReset}
                style={{
                  padding: '12px 20px',
                  backgroundColor: '#f56565',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 'bold',
                  transition: 'all 0.3s'
                }}
                onMouseOver={(e) => e.target.style.backgroundColor = '#e53e3e'}
                onMouseOut={(e) => e.target.style.backgroundColor = '#f56565'}
              >
                🗑️ Reset Sequence
              </button>
              <div style={{ 
                marginTop: '10px',
                padding: '12px',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderRadius: '6px',
                border: '1px solid #667eea'
              }}>
                <p style={{ 
                  color: '#cbd5e0', 
                  fontSize: '13px', 
                  margin: 0,
                  lineHeight: '1.6'
                }}>
                  <strong style={{ color: '#00d4ff' }}>Test Data:</strong><br/>
                  • {mockCategories.length} categories<br/>
                  • {mockPrerolls.length} prerolls<br/>
                  • {sequence.length} blocks in sequence
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Sequence Builder Component */}
        <SequenceBuilder
          initialSequence={sequence}
          categories={mockCategories}
          prerolls={mockPrerolls}
          onSave={handleSave}
          onCancel={handleCancel}
        />

        {/* Testing Instructions */}
        <div style={{ 
          marginTop: '30px',
          padding: '20px',
          backgroundColor: 'rgba(0,0,0,0.3)',
          borderRadius: '8px',
          border: '2px solid #4a5568'
        }}>
          <h2 style={{ color: '#00d4ff', fontSize: '18px', marginTop: 0 }}>
            📝 Testing Instructions
          </h2>
          <div style={{ color: '#cbd5e0', fontSize: '14px', lineHeight: '1.8' }}>
            <h3 style={{ color: '#e2e8f0', fontSize: '16px' }}>Quick Tests:</h3>
            <ol style={{ paddingLeft: '20px' }}>
              <li>Click "Add Random Block" - select category, set count, save</li>
              <li>Click "Add Fixed Block" - select 2-3 prerolls, reorder them, save</li>
              <li>Drag blocks by the drag handle (⋮⋮) to reorder</li>
              <li>Click "Edit" on any block to modify it</li>
              <li>Click "Duplicate" to copy a block</li>
              <li>Click "Delete" to remove a block</li>
              <li>Click "Preview" to see timeline view</li>
              <li>Click "Save Sequence" to test the save callback</li>
            </ol>
            
            <h3 style={{ color: '#e2e8f0', fontSize: '16px', marginTop: '20px' }}>What to Check:</h3>
            <ul style={{ paddingLeft: '20px' }}>
              <li>✅ All buttons work correctly</li>
              <li>✅ Drag-and-drop is smooth</li>
              <li>✅ Modals open and close properly</li>
              <li>✅ Block numbers update when reordering</li>
              <li>✅ Preview shows accurate information</li>
              <li>✅ Console shows no errors (F12)</li>
              <li>✅ JSON output looks correct</li>
            </ul>

            <h3 style={{ color: '#e2e8f0', fontSize: '16px', marginTop: '20px' }}>Console Commands:</h3>
            <pre style={{ 
              backgroundColor: '#000',
              padding: '10px',
              borderRadius: '4px',
              fontSize: '12px',
              color: '#0f0',
              overflow: 'auto'
            }}>
{`// Check for errors
console.log('Errors:', window.__reactErrors || 'none');

// View current sequence
console.log('Sequence:', ${JSON.stringify(sequence, null, 2)});

// Test validation
import { validateSequence } from './utils/sequenceValidator';
validateSequence(sequence, mockCategories, mockPrerolls);`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

export default TestSequenceBuilder;
