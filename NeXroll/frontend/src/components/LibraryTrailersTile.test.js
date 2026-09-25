import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import LibraryTrailersTile from './LibraryTrailersTile';
const apiUrl = p => '/'+p;
const data = { config:{enabled:true,max_gb:5}, radarr_connected:true,
  summary:{local:3,downloaded:4,downloaded_gb:1.2,outside:2,errors:1}, sync:{running:false} };
beforeEach(() => { global.fetch=jest.fn(); });
afterEach(() => { jest.useRealTimers(); });
const reply = (value, ok=true) => Promise.resolve({ok,json:async()=>value});
test('sync uses only Library Trailers, disables repeated clicks and refreshes completion', async () => {
  jest.useFakeTimers();let current=data;
  fetch.mockImplementation((url,options)=>options?.method==='POST' ? reply({started:true}) : reply(current));
  render(<LibraryTrailersTile apiUrl={apiUrl} onOpen={()=>{}} />);
  const button=await screen.findByRole('button',{name:'Sync Library Trailers'});
  await waitFor(()=>expect(button).toBeEnabled());
  fireEvent.click(button);fireEvent.click(button);
  await waitFor(()=>expect(screen.getByRole('button',{name:'Syncing...'})).toBeDisabled());
  expect(fetch.mock.calls.filter(([,o])=>o?.method==='POST')).toHaveLength(1);
  expect(fetch.mock.calls.find(([,o])=>o?.method==='POST')[0]).toBe('/nexup/library/sync');
  current={...data,sync:{running:false,finished_at:'2026-09-25T12:00:00'}};
  await act(async()=>{jest.advanceTimersByTime(5000);});
  expect(screen.getByRole('button',{name:'Sync Library Trailers'})).toBeEnabled();
  expect(screen.getByText(/Last sync:/)).toBeInTheDocument();
});
test.each([{enabled:false,connected:true},{enabled:true,connected:false}])('sync needs saved setup %j',async x=>{
  fetch.mockImplementation(()=>reply({...data,config:{...data.config,enabled:x.enabled},radarr_connected:x.connected}));
  render(<LibraryTrailersTile apiUrl={apiUrl} onOpen={()=>{}} />);
  await screen.findByText('available');
  expect(screen.getByRole('button',{name:'Sync Library Trailers'})).toBeDisabled();
});
test('failed status does not pretend the library is empty', async()=>{
  fetch.mockImplementation(()=>Promise.reject(new Error('Offline')));
  render(<LibraryTrailersTile apiUrl={apiUrl} onOpen={()=>{}} />);
  expect(await screen.findByText('Offline')).toBeInTheDocument();
  expect(screen.queryByText('available')).not.toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Sync Library Trailers'})).toBeDisabled();
});

test('background refresh keeps existing counts visible while pending, failed and recovered', async()=>{
  jest.useFakeTimers();
  fetch.mockImplementation(()=>reply(data));
  render(<LibraryTrailersTile apiUrl={apiUrl} onOpen={()=>{}} />);
  await screen.findByText('available');
  const count=screen.getByText('available').parentElement;
  let rejectRefresh;
  fetch.mockImplementationOnce(()=>new Promise((resolve,reject)=>{rejectRefresh=reject;}));
  await act(async()=>{jest.advanceTimersByTime(5000);});
  expect(count).toHaveTextContent('7 available');
  expect(screen.queryByText('Loading Library Trailers...')).not.toBeInTheDocument();
  await act(async()=>{rejectRefresh(new Error('Temporary connection failure'));});
  expect(screen.getByRole('alert')).toHaveTextContent('Temporary connection failure');
  expect(count).toHaveTextContent('7 available');
  fetch.mockImplementation(()=>reply({...data,summary:{...data.summary,downloaded:5}}));
  await act(async()=>{jest.advanceTimersByTime(5000);});
  expect(screen.getByText('available').parentElement).toBe(count);
  expect(count).toHaveTextContent('8 available');
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
