import React, { useState } from 'react';
import { Layout, Menu, Button, Progress, message, Spin } from 'antd';
import {
  DashboardOutlined,
  TagsOutlined,
  ClusterOutlined,
  RiseOutlined,
  GlobalOutlined,
  AimOutlined,
  TableOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  ForkOutlined,
  AppstoreOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation, Outlet } from 'react-router-dom';
import {
  usePipelineStatus,
  useSummary,
  useDailyCounts,
  useCategories,
  useTopics,
  useIntents,
  useLanguage,
  useTrends,
  useThemeSummary,
  useEffectAnalysis,
  useRetention,
  useUserPath,
  useBERTopic,
  useHotTemplates,
  useUserSegments,
  useInvalidateCoreData,
} from '../../hooks/useAnalysisData';
import { syncAndAnalyze } from '../../api/endpoints';

// Prefetch all core data once at app load so every tab reads from cache.
function useGlobalPrefetch() {
  useSummary();
  useDailyCounts();
  useCategories();
  useTopics();
  useIntents();
  useLanguage();
  useTrends();
  useThemeSummary();
  useEffectAnalysis('like_count');
  useRetention();
  useUserPath();
  useBERTopic();
  useHotTemplates();
  useUserSegments();
}

const { Sider, Content, Header } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '总览' },
  { key: '/categories', icon: <TagsOutlined />, label: '分类标签' },
  { key: '/topics', icon: <ClusterOutlined />, label: '主题聚类' },
  { key: '/trends', icon: <RiseOutlined />, label: '趋势分析' },
  { key: '/language', icon: <GlobalOutlined />, label: '语言与质量' },
  { key: '/intents', icon: <AimOutlined />, label: '意图分析' },
  { key: '/explorer', icon: <TableOutlined />, label: '数据浏览' },
  { key: '/paths', icon: <ForkOutlined />, label: '创作路径' },
  { key: '/effects', icon: <ThunderboltOutlined />, label: '效果分析' },
  { key: '/topic-analysis', icon: <AppstoreOutlined />, label: '主题分析' },
  { key: '/templates', icon: <FileTextOutlined />, label: '爆款模板' },
];

const STEP_LABELS: Record<string, string> = {
  '正在增量同步最新数据...': '增量同步数据',
  '加载数据...': '加载数据',
  'Detecting languages': '语言检测',
  'Computing text statistics': '文本统计',
  'Extracting keywords (TF-IDF)': '关键词提取',
  'Building topic model (LDA + t-SNE)': '主题建模',
  'Analyzing trends': '趋势分析',
  'Classifying intents (Claude API)': '意图分类',
  'Assessing prompt quality (Claude API)': '质量评估',
  'Generating theme summary': '主题总结',
  'Computing user segments': '用户分层',
  'Building embedding index (FAISS)': '向量索引',
  'Running effect analysis': '效果分析',
  'Computing user retention cohorts': '留存分析',
  'Analyzing user creation paths': '创作路径',
  'Training BERTopic model': '主题模型',
  'Mining hot prompt templates': '爆款模板',
  'Running effect analysis (multi-metric)': '多指标效果分析',
  'Finalizing': '完成收尾',
};

function localizeStep(step: string): string {
  for (const [key, val] of Object.entries(STEP_LABELS)) {
    if (step.includes(key)) return val;
  }
  return step;
}

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const { data: pipelineStatus } = usePipelineStatus(syncing);
  const invalidateCoreData = useInvalidateCoreData();

  useGlobalPrefetch();

  const handleSync = async () => {
    if (syncing) return;
    try {
      setSyncing(true);
      await syncAndAnalyze();
    } catch {
      message.error('启动失败，请检查后端连接');
      setSyncing(false);
    }
  };

  // Watch pipeline status — when done, refresh all charts
  React.useEffect(() => {
    if (!syncing) return;
    if (pipelineStatus?.status === 'completed') {
      setSyncing(false);
      invalidateCoreData();
      message.success({ content: '数据已更新，图表已刷新！', duration: 4 });
    } else if (pipelineStatus?.status === 'failed') {
      setSyncing(false);
      message.error(`分析失败：${pipelineStatus.error || '未知错误'}`);
    }
  }, [pipelineStatus?.status]);

  // Parse phase info from config_json
  let phase = 'sync';
  let phaseProgress = 0;
  if (pipelineStatus?.config_json) {
    try {
      const cfg = JSON.parse(pipelineStatus.config_json);
      if (cfg.phase) phase = cfg.phase;
      if (cfg.phase_progress != null) phaseProgress = cfg.phase_progress;
    } catch { /* ignore */ }
  }

  const syncProgress = phase === 'sync' ? Math.round(phaseProgress * 100) : 100;
  const analysisProgress = phase === 'analysis' ? Math.round(phaseProgress * 100) : (phase === 'sync' ? 0 : 100);
  const stepLabel = pipelineStatus?.current_step
    ? localizeStep(pipelineStatus.current_step)
    : '';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="light"
        width={220}
        style={{
          borderRight: '1px solid #f0f0f0',
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        <div style={{
          padding: collapsed ? '16px 8px' : '16px 20px',
          fontSize: collapsed ? 14 : 18,
          fontWeight: 700,
          color: '#1677ff',
          textAlign: 'center',
          borderBottom: '1px solid #f0f0f0',
        }}>
          {collapsed ? 'PA' : 'Prompt 分析平台'}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0 }}
        />
      </Sider>
      <Layout style={{ marginLeft: collapsed ? 80 : 220, transition: 'margin-left 0.2s' }}>
        <Header style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #f0f0f0',
          height: 56,
        }}>
          <div style={{ fontSize: 16, fontWeight: 600 }}>
            Tripo Prompt 分析平台
          </div>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            {syncing && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 320 }}>
                <Spin size="small" />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 11, color: '#666', marginBottom: 4 }}>
                    {phase === 'sync' ? '数据同步中…' : `数据分析中… ${stepLabel ? `· ${stepLabel}` : ''}`}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                    <span style={{ fontSize: 10, color: '#888', width: 48, flexShrink: 0 }}>数据同步</span>
                    <Progress
                      percent={syncProgress}
                      size="small"
                      style={{ margin: 0, flex: 1 }}
                      strokeColor="#52c41a"
                      status={phase === 'sync' ? 'active' : 'success'}
                    />
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 10, color: '#888', width: 48, flexShrink: 0 }}>数据分析</span>
                    <Progress
                      percent={analysisProgress}
                      size="small"
                      style={{ margin: 0, flex: 1 }}
                      strokeColor="#1677ff"
                      status={phase === 'analysis' ? 'active' : (analysisProgress === 100 ? 'success' : 'normal')}
                    />
                  </div>
                </div>
              </div>
            )}
            <Button
              type="primary"
              icon={<SyncOutlined spin={syncing} />}
              onClick={handleSync}
              loading={syncing}
            >
              {syncing ? '同步中…' : '同步数据'}
            </Button>
          </div>
        </Header>
        <Content style={{ margin: 24, background: '#f5f5f5', minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
