import { QueryClientProvider } from '@tanstack/react-query';
import { render } from 'preact';
import { App } from './app';
import { queryClient } from './lib/query-client';
import './style.css';

render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
  document.getElementById('app')!,
);
