import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Card, List, Typography, Tag, Empty, Alert } from 'antd';
import { BulbOutlined } from '@ant-design/icons';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import KpiCard from '../components/common/KpiCard';
import { useIntents } from '../hooks/useAnalysisData';

const { Text, Paragraph } = Typography;

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911'];

interface IntentItem {
  intent: string;
  label: string;
  description: string;
  count: number;
  percentage: number;
}

interface SubIntentItem {
  intent: string;
  intent_label: string;
  sub_intent: string;
  sub_intent_label: string;
  count: number;
}

interface IntentEngagement {
  intent: string;
  label: string;
  avg_likes: number;
  total_likes: number;
  count: number;
}

interface IntentCrossData {
  intents: string[];
  categories: string[];
  matrix: number[][];
}

interface IntentV2Data {
  distribution: IntentItem[];
  sub_intent_distribution: SubIntentItem[];
  intent_category_cross: IntentCrossData;
  intent_engagement: IntentEngagement[];
  sample_prompts: Record<string, string[]>;
  insights: string[];
  sample_size: number;
  total_prompts: number;
}

const IntentPage: React.FC = () => {
  const navigate = useNavigate();
  const { data: rawData, isLoading } = useIntents();
  const data = rawData as unknown as IntentV2Data | undefined;
  const [selectedIntent, setSelectedIntent] = useState<string | null>(null);

  const distribution = data?.distribution || [];
  const subIntents = data?.sub_intent_distribution || [];
  const cross = data?.intent_category_cross;
  const engagement = data?.intent_engagement || [];
  const insights = data?.insights || [];

  // Treemap (intent distribution)
  const treemapOption = {
    tooltip: {
      formatter: (p: { name: string; value: number; data: { description?: string; percentage?: number } }) => {
        return `<b>${p.name}</b><br/>${p.value} 条 (${p.data.percentage}%)<br/><span style="color:#999">${p.data.description || ''}</span>`;
      },
    },
    series: [{
      type: 'treemap',
      data: distribution.map((d, i) => ({
        name: d.label,
        value: d.count,
        percentage: d.percentage,
        description: d.description,
        intentKey: d.intent,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      breadcrumb: { show: false },
      label: {
        show: true,
        fontSize: 14,
        formatter: (p: { data: { percentage: number }; name: string }) =>
          `${p.name}\n${p.data.percentage}%`,
      },
      levels: [{ itemStyle: { borderColor: '#fff', borderWidth: 2, gapWidth: 2 } }],
    }],
  };

  // Bar chart
  const barOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 120, right: 60, top: 10, bottom: 30 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      inverse: true,
      data: distribution.map(d => d.label),
      axisLabel: { fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: distribution.map((d, i) => ({
        value: d.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 28,
      label: {
        show: true,
        position: 'right' as const,
        formatter: (p: { value: number; dataIndex: number }) => {
          const item = distribution[p.dataIndex];
          return `${p.value.toLocaleString()} (${item?.percentage}%)`;
        },
        fontSize: 11,
      },
    }],
  };

  // Sub-intent horizontal bar
  const topSubs = subIntents.filter(s => s.intent !== 'general_other').slice(0, 12);
  const subOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 180, right: 40, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      inverse: true,
      data: topSubs.map(s => `${s.intent_label} / ${s.sub_intent_label}`),
      axisLabel: { width: 160, overflow: 'truncate' as const, fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: topSubs.map((_s, i) => ({
        value: topSubs[i].count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 20,
      label: { show: true, position: 'right' as const, fontSize: 11 },
    }],
  };

  // Intent × category heatmap
  const heatmapOption = cross ? {
    tooltip: {
      position: 'top',
      formatter: (p: { data: number[] }) => {
        const intent = cross.intents[p.data[1]];
        const cat = cross.categories[p.data[0]];
        return `${intent} × ${cat}<br/>${p.data[2].toLocaleString()} 条`;
      },
    },
    grid: { left: 100, right: 80, top: 80, bottom: 20 },
    xAxis: {
      type: 'category' as const,
      data: cross.categories,
      position: 'top' as const,
      axisLabel: { rotate: 30, fontSize: 10 },
    },
    yAxis: {
      type: 'category' as const,
      data: cross.intents,
      axisLabel: { fontSize: 11 },
    },
    visualMap: {
      min: 0,
      max: Math.max(...(cross.matrix.map(m => m[2])), 1),
      orient: 'vertical' as const,
      right: 0,
      top: 'center' as const,
      inRange: { color: ['#f0f0f0', '#1677ff'] },
    },
    series: [{
      type: 'heatmap',
      data: cross.matrix,
      label: {
        show: true,
        fontSize: 9,
        formatter: (p: { data: number[] }) => p.data[2] > 0 ? p.data[2].toString() : '',
      },
    }],
  } : null;

  // Engagement bar
  const engagementOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 120, right: 60, top: 10, bottom: 30 },
    xAxis: { type: 'value' as const, name: '平均点赞数' },
    yAxis: {
      type: 'category' as const,
      inverse: true,
      data: engagement.map(e => e.label),
      axisLabel: { fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: engagement.map((e, i) => ({
        value: e.avg_likes,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 24,
      label: {
        show: true,
        position: 'right' as const,
        formatter: (p: { value: number }) => p.value.toFixed(4),
        fontSize: 11,
      },
    }],
  };

  const samplePrompts = selectedIntent
    ? data?.sample_prompts?.[selectedIntent] || []
    : [];
  const selectedLabel = selectedIntent
    ? distribution.find(d => d.intent === selectedIntent)?.label || selectedIntent
    : '';

  return (
    <div>
      {/* Header */}
      <Alert
        type="info"
        showIcon
        icon={<BulbOutlined />}
        message="🎯 意图分析：基于 Prompt 语义识别用户生成需求"
        description="洞察用户为什么生成（创作场景），而非生成什么（对象类型），指导产品迭代、功能设计与运营策略"
        style={{ marginBottom: 16 }}
      />

      {/* Insights */}
      {insights.length > 0 && (
        <Alert
          type="success"
          showIcon
          message="业务洞察"
          description={
            <List
              size="small"
              dataSource={insights}
              renderItem={item => (
                <List.Item style={{ padding: '4px 0', border: 'none' }}>{item}</List.Item>
              )}
            />
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* KPI */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <KpiCard title="分析样本" value={data?.sample_size || 0} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="意图类别" value={distribution.length} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard
            title="明确意图占比"
            value={
              distribution.length
                ? `${(100 - (distribution.find(d => d.intent === 'general_other')?.percentage || 0)).toFixed(1)}%`
                : '-'
            }
            loading={isLoading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard
            title="最热子意图"
            value={topSubs[0]?.sub_intent_label || '-'}
            loading={isLoading}
          />
        </Col>
      </Row>

      {/* Main charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="意图矩形树图" bordered={false}>
            <EChartsWrapper
              option={treemapOption}
              loading={isLoading}
              empty={!distribution.length}
              height={420}
              onEvents={{
                click: (p: { data?: { intentKey?: string } }) => {
                  if (p?.data?.intentKey) setSelectedIntent(p.data.intentKey);
                },
              }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="意图分布条形图" bordered={false}>
            <EChartsWrapper
              option={barOption}
              loading={isLoading}
              empty={!distribution.length}
              height={420}
            />
          </Card>
        </Col>
      </Row>

      {/* Sub-intent + Engagement */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="子意图分布（Top 12）" bordered={false}>
            <EChartsWrapper option={subOption} loading={isLoading} empty={!topSubs.length} height={400} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="意图 - 效果分析（平均点赞数）" bordered={false}>
            <EChartsWrapper option={engagementOption} loading={isLoading} empty={!engagement.length} height={400} />
          </Card>
        </Col>
      </Row>

      {/* Heatmap + Samples */}
      <Row gutter={[16, 16]}>
        {heatmapOption && (
          <Col xs={24} lg={14}>
            <Card
              title="意图 × 对象类别 交叉分析（点击可下钻）"
              bordered={false}
              extra={<Text type="secondary" style={{ fontSize: 12 }}>颜色越深代表该组合数量越多</Text>}
            >
              <EChartsWrapper
                option={heatmapOption}
                loading={isLoading}
                empty={!cross?.matrix.length}
                height={400}
                onEvents={{
                  click: (p: { data?: number[] }) => {
                    if (p?.data && cross) {
                      const cat = cross.categories[p.data[0]];
                      if (cat) navigate(`/categories`);
                    }
                  },
                }}
              />
            </Card>
          </Col>
        )}
        <Col xs={24} lg={heatmapOption ? 10 : 24}>
          <Card
            title={selectedIntent ? `示例 Prompt：${selectedLabel}` : '点击树图查看示例'}
            bordered={false}
          >
            {samplePrompts.length > 0 ? (
              <List
                dataSource={samplePrompts}
                renderItem={(item, idx) => (
                  <List.Item>
                    <div>
                      <Tag color="blue">{idx + 1}</Tag>
                      <Paragraph
                        ellipsis={{ rows: 2 }}
                        style={{ display: 'inline', margin: 0, fontSize: 12 }}
                      >
                        {item}
                      </Paragraph>
                    </div>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description="点击上方树图的意图方块查看对应示例" />
            )}

            {/* Quick select tags */}
            <div style={{ marginTop: 16, borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>快速选择：</Text>
              <div style={{ marginTop: 8 }}>
                {distribution.map((d, i) => (
                  <Tag
                    key={d.intent}
                    color={selectedIntent === d.intent ? COLORS[i % COLORS.length] : undefined}
                    style={{ cursor: 'pointer', marginBottom: 4 }}
                    onClick={() => setSelectedIntent(d.intent)}
                  >
                    {d.label}
                  </Tag>
                ))}
              </div>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default IntentPage;
