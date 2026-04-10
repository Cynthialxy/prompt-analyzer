import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Row, Col, Card, Table, Tag, Select, Spin, Empty, Button, Typography } from 'antd';
import { ArrowLeftOutlined, UserOutlined } from '@ant-design/icons';
import KpiCard from '../components/common/KpiCard';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useUserSegments, useUserProfile } from '../hooks/useAnalysisData';
import type { UserSegmentUser } from '../types';

const { Text } = Typography;

const SEGMENT_COLORS: Record<string, string> = {
  power_user: '#52c41a', regular: '#1677ff', casual: '#faad14', churned: '#ff4d4f',
};
const SEGMENT_LABELS: Record<string, string> = {
  power_user: '高活跃', regular: '普通', casual: '低活跃', churned: '流失',
};

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911'];

function formatDate(d: string): string {
  if (!d) return '';
  if (d.length === 8 && !d.includes('-')) return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
  return d;
}

const UserProfilePage: React.FC = () => {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const [segmentFilter, setSegmentFilter] = useState<string | undefined>();

  // If userId is provided, show individual profile; otherwise show overview
  if (userId) {
    return <UserDetail userId={userId} navigate={navigate} />;
  }

  return <SegmentOverview segmentFilter={segmentFilter} setSegmentFilter={setSegmentFilter} navigate={navigate} />;
};

// --- Overview Component ---
const SegmentOverview: React.FC<{
  segmentFilter: string | undefined;
  setSegmentFilter: (v: string | undefined) => void;
  navigate: ReturnType<typeof useNavigate>;
}> = ({ segmentFilter, setSegmentFilter, navigate }) => {
  const { data, isLoading } = useUserSegments({ segment: segmentFilter, limit: 200 });
  const segments = data?.segments || {};
  const totalUsers = data?.total_users || 0;

  const segmentPieOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['50%', '45%'],
      label: { show: true, formatter: '{b}\n{d}%' },
      data: Object.entries(segments).map(([key, s]) => ({
        name: SEGMENT_LABELS[key] || key,
        value: s.count,
        itemStyle: { color: SEGMENT_COLORS[key] || '#999' },
      })),
    }],
  };

  const compareOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 80, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category' as const, data: Object.keys(segments).map(k => SEGMENT_LABELS[k] || k) },
    yAxis: [
      { type: 'value' as const, name: '平均 Prompt 数' },
    ],
    series: [
      {
        type: 'bar',
        name: '平均 Prompt 数',
        data: Object.values(segments).map(s => s.avg_prompts),
        itemStyle: { color: '#1677ff', borderRadius: [4, 4, 0, 0] },
      },
      {
        type: 'bar',
        name: '平均点赞数',
        data: Object.values(segments).map(s => s.avg_likes),
        itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] },
      },
    ],
  };

  const columns = [
    {
      title: '用户 ID', dataIndex: 'user_id', key: 'user_id', width: 140, ellipsis: true,
      render: (v: string) => <a onClick={() => navigate(`/users/${v}`)}>{v}</a>,
    },
    {
      title: '分层', dataIndex: 'segment', key: 'segment', width: 90,
      render: (v: string) => <Tag color={SEGMENT_COLORS[v]}>{SEGMENT_LABELS[v] || v}</Tag>,
    },
    { title: 'Prompt 数', dataIndex: 'total_prompts', key: 'total_prompts', width: 100, sorter: (a: UserSegmentUser, b: UserSegmentUser) => a.total_prompts - b.total_prompts },
    { title: '活跃天数', dataIndex: 'active_days', key: 'active_days', width: 100 },
    { title: '热门类别', dataIndex: 'top_category', key: 'top_category', width: 140, ellipsis: true },
    { title: '平均点赞', dataIndex: 'avg_like_count', key: 'avg_like_count', width: 100, sorter: (a: UserSegmentUser, b: UserSegmentUser) => a.avg_like_count - b.avg_like_count },
    { title: '最后活跃', dataIndex: 'last_seen', key: 'last_seen', width: 110, render: (v: string) => formatDate(v) },
  ];

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}><KpiCard title="总用户数" value={totalUsers} prefix={<UserOutlined />} loading={isLoading} /></Col>
        <Col xs={12} sm={6}><KpiCard title="高活跃用户" value={segments.power_user?.count || 0} loading={isLoading} /></Col>
        <Col xs={12} sm={6}><KpiCard title="普通用户" value={segments.regular?.count || 0} loading={isLoading} /></Col>
        <Col xs={12} sm={6}><KpiCard title="低活跃用户" value={segments.casual?.count || 0} loading={isLoading} /></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="用户分层分布" bordered={false}>
            <EChartsWrapper option={segmentPieOption} loading={isLoading} empty={!totalUsers} height={320} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="各分层平均指标对比" bordered={false}>
            <EChartsWrapper option={compareOption} loading={isLoading} empty={!totalUsers} height={320} />
          </Card>
        </Col>
      </Row>

      <Card
        title="用户列表"
        bordered={false}
        extra={
          <Select
            allowClear placeholder="按分层筛选" style={{ width: 150 }}
            value={segmentFilter}
            onChange={setSegmentFilter}
            options={Object.entries(SEGMENT_LABELS).map(([k, v]) => ({ label: v, value: k }))}
          />
        }
      >
        <Table
          columns={columns}
          dataSource={data?.top_users || []}
          rowKey="user_id"
          loading={isLoading}
          size="small"
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 位用户` }}
          onRow={(record) => ({
            onClick: () => navigate(`/users/${record.user_id}`),
            style: { cursor: 'pointer' },
          })}
        />
      </Card>
    </div>
  );
};

// --- Individual User Detail ---
const UserDetail: React.FC<{ userId: string; navigate: ReturnType<typeof useNavigate> }> = ({ userId, navigate }) => {
  const { data: profile, isLoading } = useUserProfile(userId);

  if (isLoading) return <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>;
  if (!profile) return <Empty description="未找到用户数据" />;

  const s = profile.summary;

  const timelineOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 60, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category' as const, data: profile.activity_timeline.map(d => formatDate(d.date)) },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'bar',
      data: profile.activity_timeline.map(d => d.count),
      itemStyle: { color: '#1677ff', borderRadius: [4, 4, 0, 0] },
    }],
  };

  const catOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 120, right: 40, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...profile.category_distribution].reverse().map(c => c.name),
    },
    series: [{
      type: 'bar',
      data: [...profile.category_distribution].reverse().map((c, i) => ({
        value: c.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 24,
    }],
  };

  const stylePieOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['30%', '55%'],
      center: ['50%', '40%'],
      data: profile.style_distribution.map((s, i) => ({
        name: s.name, value: s.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  };

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate('/users')} style={{ marginBottom: 16 }}>
        返回用户列表
      </Button>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card bordered={false}>
            <Row gutter={24} align="middle">
              <Col>
                <Text strong style={{ fontSize: 18 }}>用户 {userId.slice(0, 12)}...</Text>
                <Tag color={SEGMENT_COLORS[profile.segment]} style={{ marginLeft: 12 }}>
                  {SEGMENT_LABELS[profile.segment] || profile.segment}
                </Tag>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}><KpiCard title="总 Prompt 数" value={s.total_prompts} /></Col>
        <Col xs={12} sm={6}><KpiCard title="活跃天数" value={s.active_days} /></Col>
        <Col xs={12} sm={6}><KpiCard title="总获赞" value={s.total_likes} /></Col>
        <Col xs={12} sm={6}><KpiCard title="平均评分" value={s.avg_score} /></Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card title="活跃度时间线" bordered={false}>
            <EChartsWrapper option={timelineOption} empty={!profile.activity_timeline.length} height={250} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="类别偏好" bordered={false}>
            <EChartsWrapper option={catOption} empty={!profile.category_distribution.length} height={300} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="风格偏好" bordered={false}>
            <EChartsWrapper option={stylePieOption} empty={!profile.style_distribution.length} height={300} />
          </Card>
        </Col>
      </Row>

      <Card title="Top Prompts（按点赞排序）" bordered={false}>
        <Table
          dataSource={profile.top_prompts}
          rowKey="project_id"
          size="small"
          pagination={false}
          onRow={(r) => ({ onClick: () => navigate(`/prompt/${r.project_id}`), style: { cursor: 'pointer' } })}
          columns={[
            { title: 'Prompt', dataIndex: 'prompt', key: 'prompt', width: 350, ellipsis: true },
            { title: '类别', dataIndex: 'llm_category', key: 'cat', width: 130, render: (v: string) => v ? <Tag color="blue">{v}</Tag> : '-' },
            { title: '点赞', dataIndex: 'like_count', key: 'likes', width: 80 },
            { title: '评分', dataIndex: 'score', key: 'score', width: 80, render: (v: number) => v ?? '-' },
          ]}
        />
      </Card>
    </div>
  );
};

export default UserProfilePage;
