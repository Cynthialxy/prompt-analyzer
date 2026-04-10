export interface CategoryItem {
  name: string;
  count: number;
}

export interface SummaryData {
  total_prompts: number;
  unique_users: number;
  date_range: { min: string; max: string };
  avg_prompt_length: number;
  top_categories: CategoryItem[];
}

export interface CategoryDistributions {
  llm_category: CategoryItem[];
  llm_style: CategoryItem[];
  llm_use_case: CategoryItem[];
  llm_color: CategoryItem[];
  category_style_cross: { llm_category: string; llm_style: string; count: number }[];
}

export interface TopicCluster {
  id: number;
  label: string;
  keywords: string[];
  size: number;
  representative_prompts: string[];
}

export interface ScatterPoint {
  x: number;
  y: number;
  topic_id: number;
  prompt_preview: string;
}

export interface TopicsData {
  clusters: TopicCluster[];
  scatter_data: ScatterPoint[];
  n_topics: number;
}

export interface IntentItem {
  intent: string;
  count: number;
  percentage: number;
}

export interface IntentsData {
  distribution: IntentItem[];
  sample_prompts: Record<string, string[]>;
  sample_size: number;
  total_prompts: number;
}

export interface LanguageItem {
  language: string;
  count: number;
  percentage: number;
}

export interface TextStats {
  char_count: { mean: number; median: number; p95: number; min: number; max: number };
  word_count: { mean: number; median: number; p95: number };
  length_histogram: { range: string; count: number }[];
  lexical_diversity: { mean: number; median: number };
}

export interface LanguageData {
  language: { distribution: LanguageItem[]; total: number };
  text_stats: TextStats;
  quality: {
    summary: Record<string, { mean: number; distribution: Record<string, number> }>;
    sample_size: number;
  };
}

export interface TrendKeyword {
  keyword: string;
  recent_count: number;
  previous_count: number;
  momentum: number;
  direction: 'up' | 'down' | 'stable';
}

export interface TrendsData {
  daily_counts: { date: string; count: number }[];
  trending_keywords: TrendKeyword[];
  category_trends: { pt: string; llm_category: string; count: number }[];
  word_cloud: { name: string; value: number }[];
}

export interface PromptRecord {
  project_id: string;
  user_id: string;
  prompt: string;
  caption: string;
  name: string;
  llm_keyword: string;
  llm_object: string;
  llm_category: string;
  llm_style: string;
  llm_color: string;
  llm_use_case: string;
  llm_height: string;
  from_type: string;
  status: string;
  visibility: string;
  display_image: string;
  like_count: number;
  collect_count: number;
  score: number;
  created_at: string;
  pt: string;
}

export interface PaginatedPrompts {
  total: number;
  page: number;
  page_size: number;
  data: PromptRecord[];
}

export interface PipelineStatus {
  id?: number;
  status: string;
  current_step?: string;
  progress?: number;
  error?: string;
  started_at?: string;
  completed_at?: string;
}

export interface KeywordsData {
  keywords: { keyword: string; score: number }[];
}

// --- V1 Types (Phase 1 upgrade) ---

export interface UserSegmentSummary {
  count: number;
  percentage: number;
  avg_prompts: number;
  avg_likes: number;
}

export interface UserSegmentUser {
  user_id: string;
  segment: string;
  total_prompts: number;
  active_days: number;
  first_seen: string;
  last_seen: string;
  top_category: string;
  top_style: string;
  avg_like_count: number;
  total_like_count: number;
  avg_score: number;
}

export interface UserSegmentResponse {
  segments: Record<string, UserSegmentSummary>;
  segment_definitions: Record<string, string>;
  total_users: number;
  top_users: UserSegmentUser[];
  computed_at: string;
}

export interface UserProfile {
  user_id: string;
  segment: string;
  summary: {
    total_prompts: number;
    active_days: number;
    first_seen: string;
    last_seen: string;
    avg_likes: number;
    total_likes: number;
    total_collects: number;
    avg_score: number;
    avg_prompt_length: number;
  };
  category_distribution: CategoryItem[];
  style_distribution: CategoryItem[];
  activity_timeline: { date: string; count: number }[];
  top_prompts: {
    project_id: string;
    prompt: string;
    like_count: number;
    collect_count: number;
    score: number;
    llm_category: string;
    llm_style: string;
    created_at: string;
  }[];
}

export interface PromptAnalysis {
  project_id: string;
  prompt: string;
  intent: string;
  sub_intent: string;
  confidence: number;
  quality_score: number;
  grade: string;
  dimensions: Record<string, number>;
  optimization_suggestions: string[];
  optimized_prompt: string;
  error?: string;
}

export interface SimilarPrompt {
  project_id: string;
  prompt: string;
  similarity_score: number;
  llm_category: string;
  llm_style: string;
  like_count: number;
  collect_count: number;
  score: number;
  display_image: string;
}

export interface SimilarSearchResponse {
  query_prompt: string;
  results: SimilarPrompt[];
  index_size: number;
  model: string;
}

export interface FeatureCorrelation {
  feature: string;
  correlation: number;
  p_value: number;
  ci_low: number;
  ci_high: number;
  significant: boolean;
  direction: string;
  effect_pct: number | null;
}

export interface CategoryPerformance {
  category: string;
  avg: number;
  median: number;
  count: number;
}

export interface HitPrompt {
  project_id: string;
  prompt: string;
  like_count: number;
  collect_count: number;
  score: number | null;
  llm_category: string;
  llm_style: string;
  display_image: string;
}

// --- Phase 2 Types ---

export interface RetentionCohort {
  cohort: string;
  size: number;
  retention: Record<string, number>;
  retention_rate: Record<string, number>;
}

export interface RetentionData {
  cohorts: RetentionCohort[];
  overall: Record<string, number>;
  re_generation: {
    single_day: number;
    few_days: number;
    frequent: number;
    heavy: number;
    total_users: number;
    multi_day_users: number;
    rate: number;
  };
  avg_active_interval_days: number;
  window_days: number;
  computed_at: string;
}

export interface SankeyData {
  nodes: { name: string }[];
  links: { source: string; target: string; value: number }[];
}

export interface UserPathData {
  sankey: SankeyData;
  iteration_patterns: {
    avg_length_growth: number;
    avg_prompts_per_user: number;
    users_analyzed: number;
    users_with_growth: number;
    users_with_shrinkage: number;
  };
  top_transitions: { from: string; to: string; count: number }[];
  category_entry_exit: { category: string; in: number; out: number; stay: number }[];
  computed_at: string;
}

export interface BERTopicTopic {
  id: number;
  label: string;
  keywords: string[];
  size: number;
  representative_prompts: string[];
}

export interface TopicPromptSample {
  topic: number;
  date: string;
  platform: string;
  user_segment: string;
  like_count: number;
  collect_count: number;
  score: number;
}

export interface BERTopicData {
  topics: BERTopicTopic[];
  topic_heat_trend: { topic: number; date: string; count: number }[];
  topic_quality_link: { topic: number; label: string; size: number; avg_likes: number; avg_collects: number; avg_score: number }[];
  topic_prompt_samples?: TopicPromptSample[];
  filter_options?: {
    platforms: string[];
    user_groups: string[];
    date_range?: { min?: string; max?: string };
  };
  n_topics: number;
  model: string;
  sample_size?: number;
  computed_at?: string;
}

export interface PromptTemplate {
  id: number;
  category: string;
  style: string;
  pattern: string;
  template_prompt: string;
  examples: string[];
  avg_likes: number;
  avg_collects: number;
  avg_score: number;
  usage_count: number;
}

export interface HotTemplateData {
  templates: PromptTemplate[];
  total_hits: number;
  hit_threshold: { metric: string; value: number };
  total_templates: number;
  computed_at: string;
}

export interface EffectAnalysis {
  metric: string;
  feature_correlations: FeatureCorrelation[];
  correlation_insights: string[];
  correlation_method: string;
  correlation_sample_size: number;
  significant_count: number;
  feature_heatmap: { features: string[]; values: number[][] };
  category_performance: CategoryPerformance[];
  style_performance: { style: string; avg: number; total: number; count: number }[];
  hit_thresholds: Record<string, { p75: number; p90: number; p95: number; p99: number }>;
  hit_prompts: HitPrompt[];
  total_prompts: number;
  prompts_with_engagement: number;
}
