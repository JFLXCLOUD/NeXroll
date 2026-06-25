import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Service Worker: this app no longer uses one. Older builds registered a
// CACHE-FIRST service worker that cached preroll thumbnails/videos under
// /static/ and served them stale — and because a SW intercepts before the
// browser cache, even a hard refresh couldn't clear them. Unregister any
// leftover SW and delete its caches, then — if a stale SW is still controlling
// this page — reload exactly once to drop out of its control so media loads
// fresh from the network.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.getRegistrations()
      .then(regs => Promise.all(regs.map(reg => reg.unregister())).then(() => regs.length))
      .then(had => {
        const clearCaches = (window.caches && caches.keys)
          ? caches.keys().then(keys => Promise.all(keys.map(k => caches.delete(k)))).catch(() => {})
          : Promise.resolve();
        return clearCaches.then(() => {
          // Escape a still-controlling stale SW — once (afterwards there's no
          // controller, so this won't loop).
          if (had && navigator.serviceWorker.controller) {
            window.location.reload();
          }
        });
      })
      .catch(() => {});
  });
}

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
