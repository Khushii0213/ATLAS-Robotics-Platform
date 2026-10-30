import {describe, expect, it} from 'vitest';
import {render, screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {Layout} from './components/Layout';

describe('mission-control shell', () => {
  it('renders primary navigation', () => {
    render(<MemoryRouter><Layout /></MemoryRouter>);
    expect(screen.getByText('Command Center')).toBeTruthy();
    expect(screen.getByText('Teleoperation')).toBeTruthy();
  });
});
