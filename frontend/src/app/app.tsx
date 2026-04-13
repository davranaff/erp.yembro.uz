import { RouterProvider } from 'react-router-dom';

import { AppProviders } from '@/app/providers/app-providers';
import { appRouter } from '@/app/router/router';

export function App() {
  return (
    <AppProviders>
      <RouterProvider router={appRouter} />
    </AppProviders>
  );
}
