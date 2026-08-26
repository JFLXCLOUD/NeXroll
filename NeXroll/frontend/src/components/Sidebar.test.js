import React, { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import Sidebar from './Sidebar';

const CommunitySidebarHarness = () => {
  const [activeTab, setActiveTab] = useState('community-prerolls');
  return (
    <Sidebar
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      collapsed={false}
      onToggleCollapse={() => {}}
      mobileOpen={false}
      onCloseMobile={() => {}}
      darkMode
    />
  );
};

test('Community Prerolls exposes separate Browse and Search destinations', () => {
  render(<CommunitySidebarHarness />);

  const browse = screen.getByRole('button', { name: 'Browse' });
  const search = screen.getByRole('button', { name: 'Search' });

  expect(browse).toHaveClass('active');
  expect(search).not.toHaveClass('active');

  fireEvent.click(search);

  expect(search).toHaveClass('active');
  expect(browse).not.toHaveClass('active');
});
