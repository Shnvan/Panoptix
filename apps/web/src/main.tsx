import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import { VisitorEntryPage } from './app/components/VisitorEntryPage';
import { ThemeProvider } from './lib/theme';
import './index.css';

const publicEntryHost = 'entry.panoptix.site';

function isVisitorEntryLocation(location: Location): boolean {
  return location.hostname === publicEntryHost || location.pathname === '/entry';
}

function protectedAppHref(location: Location): string {
  return location.hostname === publicEntryHost ? 'https://panoptix.site/' : '/';
}

const rootView = isVisitorEntryLocation(window.location)
  ? <VisitorEntryPage protectedAppHref={protectedAppHref(window.location)} />
  : <App />;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      {rootView}
    </ThemeProvider>
  </StrictMode>,
);
