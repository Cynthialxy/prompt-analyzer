import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Card, Table, Tag, Select, Typography, Alert, List, Button } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, ReloadOutlined } from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import KpiCard from '../components/common/KpiCard';
import { useEffectAnalysis } from '../hooks/useAnalysisData';
import type { HitPrompt } from '../types';

const { Text } = Typography;

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911'];

const METRIC_LABELS: Record<string, string> = {
  like_count: '点赞数', collect_count: '收藏数', score: '评分',
};

interface CorrelationItem {
  feature: string;
  correlation: number;
  p_value: number;
  ci_low: number;
  ci_high: number;
  significant: boolean;
  direction: string;
  effect_pct: number | null;
}

const EffectAnalysisPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [metric, setMetric] = useState('like_count');
  const { data, isLoading } = useEffectAnalysis(metric);

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['effect-analysis'] });
  };

  const correlations: CorrelationItem[] = data?.feature_correlations || [];
  const insights: string[] = data?.correlation_insights || [];
  const catPerf = data?.category_performance || [];
  const stylePerf = data?.style_performance || [];
  const hitPrompts = data?.hit_prompts || [];
  const thresholds = data?.hit_thresholds?.[metric] || {};
  const heatmap = data?.feature_heatmap || {};
  const sigCount = data?.significant_count || 0;
  const corrSampleSize = data?.correlation_sample_size || 0;

  // --- Top 5 significant correlations ---
  const sigCorrelations = correlations.filter(c => c.significant);
  const topPositive = sigCorrelations.filter(c => c.direction === 'positive').slice(0, 5);

  // Correlation bar chart (color-coded by significance)
  const corrOption = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: { name: string; value: number; dataIndex: number }[]) => {
        const p = params[0];
        const item = [...correlations].reverse()[p.dataIndex];
        if (!item) return '';
        const sig = item.significant ? '<span style="color:#52c41a">显著</span>' : '<span style="color:#999">不显著</span>';
        let tip = `<b>${item.feature}</b><br/>Spearman r = ${item.correlation}<br/>p 值 = ${item.p_value}<br/>95%CI: [${item.ci_low}, ${item.ci_high}]<br/>${sig}`;
        if (item.effect_pct != null) tip += `<br/>效果提升: ${item.effect_pct > 0 ? '+' : ''}${item.effect_pct}%`;
        return tip;
      },
    },
    grid: { left: 180, right: 60, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const, min: -1, max: 1 },
    yAxis: {
      type: 'category' as const,
      data: [...correlations].reverse().map(c => c.feature),
      axisLabel: { fontSize: 11, width: 160, overflow: 'truncate' as const },
    },
    series: [{
      type: 'bar',
      data: [...correlations].reverse().map(c => ({
        value: c.correlation,
        itemStyle: {
          color: !c.significant ? '#d9d9d9'
            : c.direction === 'positive' ? '#52c41a'
            : '#ff4d4f',
        },
      })),
      barMaxWidth: 20,
      label: {
        show: true,
        position: 'right' as const,
        formatter: (p: { value: number; dataIndex: number }) => {
          const item = [...correlations].reverse()[p.dataIndex];
          if (!item) return '';
          const star = item.significant ? ' *' : '';
          return `${p.value.toFixed(3)}${star}`;
        },
        fontSize: 11,
      },
    }],
  };

  // Feature heatmap
  const heatmapOption = heatmap.features?.length ? {
    tooltip: {
      position: 'top',
      formatter: (p: { data: (number | null)[] }) => {
        const f1 = heatmap.features[p.data[0] as number];
        const f2 = heatmap.features[p.data[1] as number];
        const r = p.data[2];
        if (r == null) return `${f1} × ${f2}<br/>r = 无数据`;
        return `${f1} × ${f2}<br/>r = ${Number(r).toFixed(3)}`;
      },
    },
    grid: { left: 160, right: 40, top: 160, bottom: 20 },
    xAxis: {
      type: 'category' as const,
      data: heatmap.features,
      position: 'top' as const,
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: {
      type: 'category' as const,
      data: heatmap.features,
      axisLabel: { fontSize: 10 },
    },
    visualMap: {
      min: -1, max: 1, orient: 'vertical' as const, right: 0, top: 'center' as const,
      inRange: { color: ['#ff4d4f', '#fff', '#52c41a'] },
    },
    series: [{
      type: 'heatmap',
      data: heatmap.values || [],
      label: {
        show: true,
        fontSize: 9,
        formatter: (p: { data: (number | null)[] }) => {
          const r = p.data[2];
          if (r == null) return '-';
          return r === 1 ? '1' : r === 0 ? '0' : Number(r).toFixed(2);
        },
      },
    }],
  } : null;

  // Category performance bar chart
  const catPerfOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 160, right: 60, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...catPerf].slice(0, 15).reverse().map(c => c.category),
      axisLabel: { width: 140, overflow: 'truncate' as const, fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: [...catPerf].slice(0, 15).reverse().map((c, i) => ({
        value: c.avg,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 24,
      label: { show: true, position: 'right' as const, fontSize: 11, formatter: (p: { value: number }) => p.value.toFixed(4) },
    }],
  };

  // Style performance
  const stylePerfOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 120, right: 60, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...stylePerf].slice(0, 10).reverse().map(s => s.style),
    },
    series: [{
      type: 'bar',
      data: [...stylePerf].slice(0, 10).reverse().map((s, i) => ({
        value: s.avg,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 20,
      label: { show: true, position: 'right' as const, fontSize: 11, formatter: (p: { value: number }) => p.value.toFixed(4) },
    }],
  };

  // Hit prompts table
  const hitColumns = [
    {
      title: 'Prompt', dataIndex: 'prompt', key: 'prompt', width: 350, ellipsis: true,
      render: (text: string, record: HitPrompt) => (
        <a onClick={() => navigate(`/prompt/${record.project_id}`)}>{text}</a>
      ),
    },
    { title: '类别', dataIndex: 'llm_category', key: 'cat', width: 130, render: (v: string) => v ? <Tag color="blue">{v}</Tag> : '-' },
    { title: '风格', dataIndex: 'llm_style', key: 'style', width: 100, render: (v: string) => v ? <Tag color="green">{v}</Tag> : '-' },
    { title: '点赞', dataIndex: 'like_count', key: 'likes', width: 80, sorter: (a: HitPrompt, b: HitPrompt) => a.like_count - b.like_count },
    { title: '收藏', dataIndex: 'collect_count', key: 'collects', width: 80 },
    { title: '评分', dataIndex: 'score', key: 'score', width: 80, render: (v: number | null) => v != null ? v.toFixed(1) : '-' },
  ];

  return (
    <div>
      {/* Metric selector + summary */}
      <Card bordered={false} style={{ marginBottom: 16 }}>
        <Row align="middle" gutter={16}>
          <Col>
            <span style={{ marginRight: 8 }}>效果指标：</span>
            <Select value={metric} onChange={setMetric} style={{ width: 160 }}
              options={Object.entries(METRIC_LABELS).map(([k, v]) => ({ label: v, value: k }))} />
            <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={isLoading} style={{ marginLeft: 8 }}>
              刷新
            </Button>
          </Col>
          <Col flex="auto">
            <Text type="secondary">
              共 {data?.total_prompts?.toLocaleString()} 条 Prompt，
              {data?.prompts_with_engagement?.toLocaleString()} 条有{METRIC_LABELS[metric]}数据
              {corrSampleSize > 0 && ` | 相关性分析样本：${corrSampleSize} 条（仅有效数据）`}
              {data?.correlation_method && ` | 方法：${data.correlation_method}`}
            </Text>
          </Col>
        </Row>
      </Card>

      {/* Insights */}
      {insights.length > 0 && (
        <Alert
          type="info" showIcon
          message="分析洞察"
          description={
            <List size="small" dataSource={insights}
              renderItem={item => <List.Item style={{ padding: '4px 0', border: 'none' }}>{item}</List.Item>} />
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Thresholds */}
      {thresholds.p90 > 0 && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={6}><KpiCard title="P75" value={thresholds.p75} loading={isLoading} /></Col>
          <Col xs={6}><KpiCard title="P90（爆款线）" value={thresholds.p90} loading={isLoading} /></Col>
          <Col xs={6}><KpiCard title="P95" value={thresholds.p95} loading={isLoading} /></Col>
          <Col xs={6}><KpiCard title="P99" value={thresholds.p99} loading={isLoading} /></Col>
        </Row>
      )}

      {/* Top 5 significant + Correlation chart */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={8}>
          <Card title={`显著相关特征 Top 5（${sigCount} 个显著）`} bordered={false}>
            {topPositive.length > 0 ? (
              <List
                dataSource={topPositive}
                renderItem={(item, idx) => (
                  <List.Item>
                    <div style={{ width: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text strong>{idx + 1}. {item.feature}</Text>
                        <Tag color={item.direction === 'positive' ? 'green' : 'red'}>
                          r={item.correlation}
                        </Tag>
                      </div>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        p={item.p_value} | CI [{item.ci_low}, {item.ci_high}]
                        {item.effect_pct != null && (
                          <span style={{ color: item.effect_pct > 0 ? '#52c41a' : '#ff4d4f', marginLeft: 8 }}>
                            {item.effect_pct > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                            {' '}{Math.abs(item.effect_pct)}%
                          </span>
                        )}
                      </Text>
                    </div>
                  </List.Item>
                )}
              />
            ) : (
              <Text type="secondary">暂无显著正相关特征（p&lt;0.05）</Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card
            title={`特征与${METRIC_LABELS[metric]}的相关性（Spearman，绿=正相关 / 红=负相关 / 灰=不显著）`}
            bordered={false}
          >
            <EChartsWrapper option={corrOption} loading={isLoading} empty={!correlations.length} height={380} />
          </Card>
        </Col>
      </Row>

      {/* Heatmap + Category Performance */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {heatmapOption && (
          <Col xs={24} lg={12}>
            <Card title="特征间共线性热力图" bordered={false}>
              <EChartsWrapper option={heatmapOption} height={400} />
              <Alert
                type="info"
                showIcon
                style={{ marginTop: 12, lineHeight: 1.8 }}
                description={
                  <>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ fontWeight: 600 }}>长度特征高度冗余</span>：图表中深绿色区域集中在「Prompt 长度」、「词数」、「长/超长 Prompt」之间，它们的相关性均大于 0.75。这说明在衡量 Prompt 长度时，这四个指标描述的是同一件事，后续分析只需保留「Prompt 长度」即可。
                    </div>
                    <div style={{ marginBottom: 4 }}>
                      <span style={{ fontWeight: 600 }}>内容维度独立性强</span>：仔细看「含颜色」、「含风格」、「含细节」等内容特征，它们之间的格子基本接近白色（r接近0）。这意味着用户的这些写作习惯是互相独立的，可以作为评价 Prompt 质量的独立维度。
                    </div>
                    <div>
                      <span style={{ fontWeight: 600 }}>字多不等于细节多</span>：最下方「长度类」与「内容类」特征交界的区域颜色很浅，说明即使 Prompt 写得很长，也不必然意味着用户使用了更多专业的参数标签或细节描述。
                    </div>
                  </>
                }
              />
            </Card>
          </Col>
        )}
        <Col xs={24} lg={heatmapOption ? 12 : 24}>
          <Card title={`各类别平均${METRIC_LABELS[metric]}`} bordered={false}>
            <EChartsWrapper option={catPerfOption} loading={isLoading} empty={!catPerf.length} height={400} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card title={`各风格平均${METRIC_LABELS[metric]}`} bordered={false}>
            <EChartsWrapper option={stylePerfOption} loading={isLoading} empty={!stylePerf.length} height={300} />
          </Card>
        </Col>
      </Row>

      {/* Hit Prompts Table */}
      <Card title={`爆款 Prompt（${METRIC_LABELS[metric]} >= P90）`} bordered={false}>
        <Table columns={hitColumns} dataSource={hitPrompts} rowKey="project_id"
          loading={isLoading} size="small" pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 900 }} />
      </Card>
    </div>
  );
};

export default EffectAnalysisPage;
