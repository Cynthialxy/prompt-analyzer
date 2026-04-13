import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
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
import UserProfilePage from './pages/UserProfilePage';
import EffectAnalysisPage from './pages/EffectAnalysisPage';
import UserRetentionPage from './pages/UserRetentionPage';
import UserPathPage from './pages/UserPathPage';
import TopicAnalysisPage from './pages/TopicAnalysisPage';
import TemplateMarketPage from './pages/TemplateMarketPage';

// Data is shared globally via React Query cache.
// staleTime: 5 minutes — tab switches reuse cached data, no duplicate requests.
// gcTime: 10 minutes — keep data in memory even when no component is subscribed.
const STALE_TIME = 5 * 60 * 1000;
const GC_TIME = 10 * 60 * 1000;

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

function App() {
  return (
    <QueryClientProvider client={queryClient}>
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
    </QueryClientProvider>
  );
}

export default App;
