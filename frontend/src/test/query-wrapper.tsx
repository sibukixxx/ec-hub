import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ComponentChildren } from 'preact';

export function createQueryWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });

  function Wrapper({ children }: { children: ComponentChildren }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  }

  return { client, Wrapper };
}
