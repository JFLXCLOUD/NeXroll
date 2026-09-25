import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import Sidebar from './Sidebar';
const apiUrl = p=>'/'+p;
function Harness({scope='user:1',close=()=>{},collapsed=false}) {
  const [activeTab,setActiveTab]=useState('nexup/library');
  return <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} apiUrl={apiUrl} favoriteScope={scope}
    collapsed={collapsed} onCloseMobile={close} darkMode />;
}
beforeEach(()=>{ global.fetch=jest.fn(); });
test('favorite persists via server across remounts and navigates in collapsed mode',async()=>{
  let pages=[];
  fetch.mockImplementation(async(url,options)=>{
    if(options?.method==='PUT') pages=JSON.parse(options.body).favorite?['nexup/library']:[];
    return {ok:true,json:async()=>({pages})};
  });
  const first=render(<Harness />);
  const add=screen.getByRole('button',{name:'Favorite this page'});
  await waitFor(()=>expect(add).toBeEnabled());fireEvent.click(add);
  const region=screen.getByRole('region',{name:'Favorites'});
  expect(await within(region).findByRole('button',{name:'NeX-Up · Library Trailers'})).toBeInTheDocument();
  first.unmount();
  const close=jest.fn();render(<Harness close={close} collapsed />);
  const shortcut=await within(screen.getByRole('region',{name:'Favorites'})).findByRole('button',{name:'NeX-Up · Library Trailers'});
  fireEvent.click(shortcut);expect(close).toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Remove this page from Favorites'}));
  await waitFor(()=>expect(shortcut).not.toBeInTheDocument());
  expect(pages).toEqual([]);
});
test('failed save keeps the previous list and explains failure',async()=>{
  fetch.mockImplementation(async(url,options)=>options?.method==='PUT'
    ? {ok:false,json:async()=>({detail:'Unavailable'})} : {ok:true,json:async()=>({pages:[]})});
  render(<Harness />);
  const add=screen.getByRole('button',{name:'Favorite this page'});
  await waitFor(()=>expect(add).toBeEnabled());fireEvent.click(add);
  expect(await screen.findByText('Favorites could not be saved. Try again.')).toBeInTheDocument();
  expect(add).toHaveAttribute('aria-pressed','false');
  expect(within(screen.getByRole('region',{name:'Favorites'})).queryByRole('button',{name:'NeX-Up · Library Trailers'})).not.toBeInTheDocument();
});
test('switching accounts clears shortcuts before loading the new owner',async()=>{
  fetch.mockResolvedValue({ok:true,json:async()=>({pages:['nexup/library']})});
  const {rerender}=render(<Harness />);
  const shortcut=await within(screen.getByRole('region',{name:'Favorites'})).findByRole('button',{name:'NeX-Up · Library Trailers'});
  fetch.mockResolvedValue({ok:true,json:async()=>({pages:[]})});
  rerender(<Harness scope="user:2" />);
  expect(shortcut).not.toBeInTheDocument();
  await waitFor(()=>expect(screen.getByRole('button',{name:'Favorite this page'})).toBeEnabled());
});
