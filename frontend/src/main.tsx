import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from '@/app/app';
import '@/app/styles/styles.css';

const root = document.getElementById('root');

if (!root) {
  throw new Error('Root container missing');
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
