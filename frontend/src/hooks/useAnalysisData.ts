import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchSummary,
  fetchCategories,
  fetchTopics,
  fetchIntents,
  fetchLanguage,
  fetchTrends,
  fetchKeywords,
  fetchThemeSummary,
  fetchPipelineStatus,
  fetchDailyCounts,
  fetchUserSegments,
  fetchUserProfile,
  fetchPromptIntent,
  fetchPromptSimilar,
  fetchEffectAnalysis,
  fetchRetention,
  fetchUserPath,
  fetchBERTopic,
  fetchHotTemplates,
} from '../api/endpoints';

// All core query keys — used for cache invalidation after pipeline completes.
export const CORE_QUERY_KEYS = [
  ['summary'],
  ['daily-counts'],
  ['categories'],
  ['topics'],
  ['intents'],
  ['language'],
  ['trends'],
  ['keywords'],
  ['theme-summary'],
  ['effect-analysis'],
  ['retention'],
  ['user-path'],
  ['bertopic'],
  ['hot-templates'],
  ['user-segments'],
];

// Call this after pipeline completes to force all tabs to reload fresh data.
export const useInvalidateCoreData = () => {
  const queryClient = useQueryClient();
  return () => {
    CORE_QUERY_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: key }));
  };
};

export const useSummary = (dateRange?: { date_from?: string; date_to?: string }) =>
  useQuery({
    queryKey: ['summary', dateRange?.date_from, dateRange?.date_to],
    queryFn: () => fetchSummary(dateRange),
  });

export const useDailyCounts = (dateRange?: { date_from?: string; date_to?: string }) =>
  useQuery({
    queryKey: ['daily-counts', dateRange?.date_from, dateRange?.date_to],
    queryFn: () => fetchDailyCounts(dateRange),
  });

export const useCategories = () =>
  useQuery({ queryKey: ['categories'], queryFn: fetchCategories });

export const useTopics = () =>
  useQuery({ queryKey: ['topics'], queryFn: fetchTopics });

export const useIntents = () =>
  useQuery({ queryKey: ['intents'], queryFn: fetchIntents });

export const useLanguage = () =>
  useQuery({ queryKey: ['language'], queryFn: fetchLanguage });

export const useTrends = () =>
  useQuery({ queryKey: ['trends'], queryFn: fetchTrends });

export const useKeywords = () =>
  useQuery({ queryKey: ['keywords'], queryFn: fetchKeywords });

export const useThemeSummary = () =>
  useQuery({ queryKey: ['theme-summary'], queryFn: fetchThemeSummary });

export const useEffectAnalysis = (metric?: string) =>
  useQuery({
    queryKey: ['effect-analysis', metric],
    queryFn: () => fetchEffectAnalysis(metric),
  });

export const useRetention = () =>
  useQuery({ queryKey: ['retention'], queryFn: fetchRetention });

export const useUserPath = () =>
  useQuery({ queryKey: ['user-path'], queryFn: fetchUserPath });

export const useBERTopic = () =>
  useQuery({ queryKey: ['bertopic'], queryFn: fetchBERTopic });

export const useHotTemplates = (metric?: string) =>
  useQuery({
    queryKey: ['hot-templates', metric],
    queryFn: () => fetchHotTemplates(metric),
  });

export const usePromptAnalysis = (projectId: string) =>
  useQuery({
    queryKey: ['prompt-analysis', projectId],
    queryFn: () => fetchPromptIntent(projectId),
    enabled: !!projectId,
  });

export const useSimilarPrompts = (projectId: string) =>
  useQuery({
    queryKey: ['similar-prompts', projectId],
    queryFn: () => fetchPromptSimilar({ project_id: projectId, top_k: 10 }),
    enabled: !!projectId,
  });

export const useUserSegments = (params?: { segment?: string; sort_by?: string; limit?: number }) =>
  useQuery({
    queryKey: ['user-segments', params?.segment, params?.sort_by, params?.limit],
    queryFn: () => fetchUserSegments(params),
  });

export const useUserProfile = (userId: string) =>
  useQuery({
    queryKey: ['user-profile', userId],
    queryFn: () => fetchUserProfile(userId),
    enabled: !!userId,
  });

export const usePipelineStatus = (enabled: boolean = false) =>
  useQuery({
    queryKey: ['pipeline-status'],
    queryFn: fetchPipelineStatus,
    refetchInterval: enabled ? 3000 : false,
  });
