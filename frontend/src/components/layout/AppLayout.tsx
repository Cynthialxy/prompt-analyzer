import React, { useState } from 'react';
import { Layout, Menu, Button, Progress, message } from 'antd';
import {
  DashboardOutlined,
  TagsOutlined,
  ClusterOutlined,
  RiseOutlined,
  GlobalOutlined,
  AimOutlined,
  TableOutlined,
  SyncOutlined,
  PlayCircleOutlined,
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
import { runPipeline, syncData } from '../../api/endpoints';

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

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [pipelinePolling, setPipelinePolling] = useState(false);
  const { data: pipelineStatus } = usePipelineStatus(pipelinePolling);
  const invalidateCoreData = useInvalidateCoreData();

  // Trigger all core queries at app load — results are cached and reused by each tab.
  useGlobalPrefetch();

  const handleSync = async () => {
    try {
      message.loading({ content: '正在从 Athena 同步数据...', key: 'sync' });
      const result = await syncData();
      message.success({ content: `已同步 ${result.count} 条 Prompt`, key: 'sync' });
    } catch {
      message.error({ content: '同步失败', key: 'sync' });
    }
  };

  const handleRunPipeline = async () => {
    try {
      await runPipeline();
      setPipelinePolling(true);
      message.info('分析管线已启动');
    } catch {
      message.error('启动分析管线失败');
    }
  };

  React.useEffect(() => {
    if (pipelineStatus?.status === 'completed' || pipelineStatus?.status === 'failed') {
      setPipelinePolling(false);
      if (pipelineStatus.status === 'completed') {
        // Pipeline produced new data — invalidate all cached queries so every tab reloads.
        invalidateCoreData();
        message.success('分析管线已完成！');
      } else {
        message.error(`分析管线失败：${pipelineStatus.error}`);
      }
    }
  }, [pipelineStatus?.status]);

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
            {pipelinePolling && pipelineStatus && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 200 }}>
                <Progress
                  percent={Math.round((pipelineStatus.progress || 0) * 100)}
                  size="small"
                  style={{ margin: 0, flex: 1 }}
                />
                <span style={{ fontSize: 12, color: '#666', whiteSpace: 'nowrap' }}>
                  {pipelineStatus.current_step}
                </span>
              </div>
            )}
            <Button icon={<SyncOutlined />} onClick={handleSync}>
              同步数据
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleRunPipeline}
              loading={pipelinePolling}
            >
              运行分析
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
