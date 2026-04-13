import client from './client';
import type {
  SummaryData,
  CategoryDistributions,
  TopicsData,
  IntentsData,
  LanguageData,
  TrendsData,
  PaginatedPrompts,
  PipelineStatus,
  KeywordsData,
} from '../types';

// Data endpoints
export const fetchSummary = (params?: { date_from?: string; date_to?: string }) =>
  client.get<SummaryData>('/data/summary', { params }).then(r => r.data);

export const fetchPrompts = (params: {
  page?: number;
  page_size?: number;
  search?: string;
  category?: string;
  style?: string;
}) =>
  client.get<PaginatedPrompts>('/data/prompts', { params }).then(r => r.data);

export const syncData = () =>
  client.post('/data/sync').then(r => r.data);

export const syncAndAnalyze = () =>
  client.post<{ status: string; run_id: number }>('/data/sync-and-analyze').then(r => r.data);

export const fetchDailyCounts = (params?: { date_from?: string; date_to?: string }) =>
  client.get<{ date: string; count: number }[]>('/data/daily-counts', { params }).then(r => r.data);

export const exportCsv = () =>
  client.get('/data/export', { responseType: 'blob' }).then(r => {
    const url = window.URL.createObjectURL(new Blob([r.data]));
    const a = document.createElement('a');
    a.href = url;
    a.download = 'prompts_export.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  });

// Analysis endpoints
export const fetchCategories = () =>
  client.get<CategoryDistributions>('/analysis/categories').then(r => r.data);

export const fetchTopics = () =>
  client.get<TopicsData>('/analysis/topics').then(r => r.data);

export const fetchIntents = () =>
  client.get<IntentsData>('/analysis/intents').then(r => r.data);

export const fetchLanguage = () =>
  client.get<LanguageData>('/analysis/language').then(r => r.data);

export const fetchTrends = () =>
  client.get<TrendsData>('/analysis/trends').then(r => r.data);

export const fetchKeywords = () =>
  client.get<KeywordsData>('/analysis/keywords').then(r => r.data);

export const fetchThemeSummary = () =>
  client.get<{ text: string }>('/analysis/theme-summary').then(r => r.data);

// Pipeline endpoints
export const runPipeline = () =>
  client.post<{ run_id: number; status: string }>('/pipeline/run').then(r => r.data);

export const fetchPipelineStatus = () =>
  client.get<PipelineStatus>('/pipeline/status').then(r => r.data);

// --- V1 Analysis Endpoints ---
import type {
  UserSegmentResponse,
  UserProfile,
  PromptAnalysis,
  SimilarSearchResponse,
  EffectAnalysis,
  RetentionData,
  UserPathData,
  BERTopicData,
  HotTemplateData,
} from '../types';

export const fetchPromptDetail = (projectId: string) =>
  client.get(`/data/prompt/${projectId}`).then(r => r.data);

export const fetchUserSegments = (params?: { segment?: string; sort_by?: string; limit?: number }) =>
  client.get<UserSegmentResponse>('/v1/analysis/user/segment', { params }).then(r => r.data);

export const fetchUserProfile = (userId: string) =>
  client.get<UserProfile>('/v1/analysis/user/profile', { params: { user_id: userId } }).then(r => r.data);

export const fetchPromptIntent = (projectId: string) =>
  client.get<PromptAnalysis>('/v1/analysis/prompt/intent', { params: { project_id: projectId } }).then(r => r.data);

export const fetchPromptSimilar = (params: { project_id?: string; query?: string; top_k?: number }) =>
  client.get<SimilarSearchResponse>('/v1/analysis/prompt/similar', { params }).then(r => r.data);

export const fetchPromptQuality = (projectId?: string) =>
  client.get('/v1/analysis/prompt/quality', { params: projectId ? { project_id: projectId } : {} }).then(r => r.data);

export const fetchEffectAnalysis = (metric?: string) =>
  client.get<EffectAnalysis>('/v1/analysis/effect', { params: { metric: metric || 'like_count' } }).then(r => r.data);

// --- Phase 2 ---

export const fetchRetention = () =>
  client.get<RetentionData>('/v1/analysis/user/retention').then(r => r.data);

export const fetchUserPath = () =>
  client.get<UserPathData>('/v1/analysis/user/path').then(r => r.data);

export const fetchBERTopic = () =>
  client.get<BERTopicData>('/v1/analysis/prompt/topics').then(r => r.data);

export const fetchHotTemplates = (metric?: string) =>
  client.get<HotTemplateData>('/v1/analysis/prompt/hot-templates', { params: { metric: metric || 'like_count' } }).then(r => r.data);
