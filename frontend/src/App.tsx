import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { createSyncStoragePersister } from '@tanstack/query-sync-storage-persister';
import { ConfigProvider } from 'antd';
import AppLayout from './components/layout/AppLayout';
import DashboardPage from './pages/DashboardPage';
import CategoryPage from './pages/CategoryPage';
import TopicPage from './pages/TopicPage';
import TrendPage from './pages/TrendPage';
import LanguagePage from './pages/LanguagePage';
import IntentPage from './pages/IntentPage';
import ExplorerPage from './pages/ExplorerPage';
import PromptDetailPage from './pages/PromptDetailPage';
import EffectAnalysisPage from './pages/EffectAnalysisPage';
import UserPathPage from './pages/UserPathPage';
import TopicAnalysisPage from './pages/TopicAnalysisPage';
import TemplateMarketPage from './pages/TemplateMarketPage';

// Cache persisted to localStorage — survives browser refresh.
// maxAge: 30 minutes. staleTime: 5 minutes (tab switches reuse cache).
const STALE_TIME = 5 * 60 * 1000;
const GC_TIME = 30 * 60 * 1000;
const MAX_AGE = 30 * 60 * 1000;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 0,
      retryOnMount: true,
      refetchOnWindowFocus: false,
      staleTime: STALE_TIME,
      gcTime: GC_TIME,
    },
  },
});

const persister = createSyncStoragePersister({
  storage: window.localStorage,
  key: 'prompt-analyzer-cache',
});

function App() {
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{ persister, maxAge: MAX_AGE }}
    >
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#1677ff',
            borderRadius: 8,
          },
        }}
      >
        <BrowserRouter>
          <Routes>
            <Route element={<AppLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/categories" element={<CategoryPage />} />
              <Route path="/topics" element={<TopicPage />} />
              <Route path="/trends" element={<TrendPage />} />
              <Route path="/language" element={<LanguagePage />} />
              <Route path="/intents" element={<IntentPage />} />
              <Route path="/explorer" element={<ExplorerPage />} />
              <Route path="/prompt/:projectId" element={<PromptDetailPage />} />
              <Route path="/effects" element={<EffectAnalysisPage />} />
              <Route path="/paths" element={<UserPathPage />} />
              <Route path="/topic-analysis" element={<TopicAnalysisPage />} />
              <Route path="/topic-analysis/:topicId" element={<TopicAnalysisPage />} />
              <Route path="/templates" element={<TemplateMarketPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ConfigProvider>
    </PersistQueryClientProvider>
  );
}

export default App;
