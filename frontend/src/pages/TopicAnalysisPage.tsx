import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Card, Tag, List, Typography, Alert } from 'antd';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import KpiCard from '../components/common/KpiCard';
import { useBERTopic } from '../hooks/useAnalysisData';
import type { BERTopicTopic } from '../types';

const { Text, Paragraph } = Typography;

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911',
  '#36cfc9', '#ffc53d', '#ff7a45', '#9254de', '#73d13d'];

const formatPerThousand = (value: number) => {
  if (value >= 100) return value.toFixed(0);
  if (value >= 10) return value.toFixed(1);
  return value.toFixed(2);
};

const formatEffectIndex = (value: number) => `${value.toFixed(1)}x`;

const formatVsPlatformText = (effectIndex: number) => {
  const percentage = Math.abs((effectIndex - 1) * 100);
  if (effectIndex >= 1) {
    return `高于平台均值${percentage.toFixed(0)}%`;
  }
  return `仅为平台均值${(effectIndex * 100).toFixed(0)}%`;
};


const getMedian = (values: number[]) => {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
};

const getEffectColor = (effectIndex: number, minEffectIndex: number, maxEffectIndex: number) => {
  if (maxEffectIndex <= minEffectIndex) return 'hsl(142 65% 42%)';
  const normalized = Math.max(0, Math.min(1, (effectIndex - minEffectIndex) / (maxEffectIndex - minEffectIndex)));
  const hue = 24 + normalized * 118;
  const lightness = 78 - normalized * 34;
  return `hsl(${Math.round(hue)} 72% ${Math.round(lightness)}%)`;
};

const getTopicBusinessName = (rawLabel: string) => {
  const tokens = rawLabel
    .toLowerCase()
    .split(',')
    .map(token => token.trim())
    .filter(Boolean);
  const has = (...values: string[]) => values.some(value => tokens.includes(value));
  const text = tokens.join(' ');

  if (has('logo', 'logos')) return 'Logo设计';
  if (has('en', 'una', 'la', 'com', 'um', 'uma')) return '多语言生成';
  if (has('3d', 'design', 'base')) return '3D设计';
  if (has('girl', 'anime')) return '动漫角色';
  if (has('poly', 'low', 'roblox')) return '低模游戏资产';
  if (has('video', 'car', '人物')) return '视频人物汽车';
  if (has('stone', 'chair', 'tree')) return '家居场景素材';
  if (has('realistic', 'style', 'body')) return '写实人物';
  if (has('pose', 'body')) return '姿态角色';
  if (has('generate', 'test')) return '通用生成测试';
  if (has('生成', '一个', '模型') || (has('make', 'model') && !has('3d'))) return '模型生成';
  if (text.includes('для') || text.includes('модель') || text.includes('ha')) return '俄语模型生成';
  if (text.includes('और') || text.includes('एक') || has('di')) return '印地语内容';
  return '内容生成';
};

const TopicAnalysisPage: React.FC = () => {
  const navigate = useNavigate();
  const { data, isLoading } = useBERTopic();
  const [selectedTopic, setSelectedTopic] = useState<number | null>(null);

  const handleTopicClick = (topicId: number) => {
    setSelectedTopic(topicId);
    // Scroll to detail panel
    document.getElementById('topic-detail-panel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  };

  const topics = data?.topics || [];
  const qualityLink = data?.topic_quality_link || [];
  const maxTopicSize = topics.length ? Math.max(...topics.map(t => t.size)) : 0;
  const selected: BERTopicTopic | undefined = selectedTopic !== null
    ? topics.find(t => t.id === selectedTopic)
    : undefined;

  const getTopicDisplayLabel = (topicId: number, fallbackLabel?: string) => {
    const matchedTopic = topics.find(t => t.id === topicId);
    const keywordLabel = matchedTopic?.keywords?.slice(0, 3).join(', ').trim();
    const rawLabel = keywordLabel
      || (fallbackLabel && !/^Topic\s+\d+$/i.test(fallbackLabel) ? fallbackLabel : `主题 ${topicId}`);
    return `${getTopicBusinessName(rawLabel)} (${rawLabel})`;
  };

  const platformAvgLikes = qualityLink.reduce((sum, item) => sum + (item.avg_likes * item.size), 0)
    / Math.max(1, qualityLink.reduce((sum, item) => sum + item.size, 0));

  const topicEffectData = qualityLink
    .map((q) => {
      const displayLabel = getTopicDisplayLabel(q.topic, q.label);
      const likesPerThousand = q.avg_likes * 1000;
      const estimatedLikes = q.avg_likes * q.size;
      const effectIndex = platformAvgLikes > 0 ? q.avg_likes / platformAvgLikes : 0;
      return {
        ...q,
        displayLabel,
        likesPerThousand,
        estimatedLikes,
        effectIndex,
      };
    })
    .filter(item => item.size > 0);

  const validEffectTopics = topicEffectData.filter(item => item.avg_likes > 0);
  const scatterDataSource = validEffectTopics.length ? validEffectTopics : topicEffectData;
  const topQualityTopics = [...scatterDataSource]
    .sort((a, b) => b.effectIndex - a.effectIndex || b.likesPerThousand - a.likesPerThousand)
    .slice(0, 10);

  const minTopicSize = scatterDataSource.length ? Math.min(...scatterDataSource.map(item => item.size)) : 0;
  const maxScatterTopicSize = scatterDataSource.length ? Math.max(...scatterDataSource.map(item => item.size)) : 0;
  const minEffectIndex = scatterDataSource.length ? Math.min(...scatterDataSource.map(item => item.effectIndex)) : 0;
  const maxEffectIndex = scatterDataSource.length ? Math.max(...scatterDataSource.map(item => item.effectIndex)) : 0;
  const labelTopicIds = new Set(
    [...scatterDataSource]
      .sort((a, b) => ((b.effectIndex * Math.log10(b.size + 1)) - (a.effectIndex * Math.log10(a.size + 1))))
      .slice(0, 4)
      .map(item => item.topic),
  );

  const getBubbleSize = (topicSize: number) => {
    if (!scatterDataSource.length || maxScatterTopicSize === minTopicSize) return 24;
    const normalized = (Math.sqrt(topicSize) - Math.sqrt(minTopicSize)) / (Math.sqrt(maxScatterTopicSize) - Math.sqrt(minTopicSize));
    return 20 + normalized * 30;
  };

  const scatterPoints = scatterDataSource.map((item) => ({
    topicId: item.topic,
    topicLabel: item.displayLabel,
    size: item.size,
    avgLikes: item.avg_likes,
    likesPerThousand: item.likesPerThousand,
    avgScore: item.avg_score || 0,
    effectIndex: item.effectIndex,
    value: [item.size, item.likesPerThousand],
    itemStyle: {
      color: getEffectColor(item.effectIndex, minEffectIndex, maxEffectIndex || 1),
      opacity: 0.88,
      shadowBlur: labelTopicIds.has(item.topic) ? 12 : 0,
      shadowColor: 'rgba(0,0,0,0.12)',
    },
    label: {
      show: labelTopicIds.has(item.topic),
      position: 'top',
      color: '#262626',
      fontSize: 11,
      formatter: () => item.displayLabel,
    },
  }));

  const regressionLineData = (() => {
    if (scatterDataSource.length < 2) return [];
    const points = scatterDataSource.map(item => ({ x: item.size, y: item.likesPerThousand }));
    const count = points.length;
    const sumX = points.reduce((sum, point) => sum + point.x, 0);
    const sumY = points.reduce((sum, point) => sum + point.y, 0);
    const sumXY = points.reduce((sum, point) => sum + (point.x * point.y), 0);
    const sumXX = points.reduce((sum, point) => sum + (point.x * point.x), 0);
    const denominator = (count * sumXX) - (sumX * sumX);
    if (denominator === 0) return [];
    const slope = ((count * sumXY) - (sumX * sumY)) / denominator;
    const intercept = (sumY - (slope * sumX)) / count;
    const minX = Math.min(...points.map(point => point.x));
    const maxX = Math.max(...points.map(point => point.x));
    return [
      [minX, Math.max(0, (slope * minX) + intercept)],
      [maxX, Math.max(0, (slope * maxX) + intercept)],
    ];
  })();

  const largeTopicThreshold = getMedian(scatterDataSource.map(item => item.size));
  const largeTopics = scatterDataSource.filter(item => item.size >= largeTopicThreshold);
  const goldenThemes = [...largeTopics]
    .sort((a, b) => ((b.effectIndex * Math.log10(b.size + 1)) - (a.effectIndex * Math.log10(a.size + 1))))
    .slice(0, 3);
  const optimizationThemes = [...largeTopics]
    .sort((a, b) => (a.effectIndex - b.effectIndex) || (b.size - a.size))
    .slice(0, 3);

  // Treemap
  const treemapOption = {
    tooltip: {
      formatter: (p: { name: string; value: number; data: { keywords?: string[] } }) => {
        const kws = p.data.keywords?.slice(0, 5).join(', ') || '';
        return `<b>${p.name}</b><br/>${p.value} 条<br/>${kws}`;
      },
    },
    series: [{
      type: 'treemap',
      data: topics.map((t, i) => ({
        name: t.keywords.slice(0, 3).join(', ') || t.label,
        value: t.size,
        keywords: t.keywords,
        topicId: t.id,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      breadcrumb: { show: false },
      label: { show: true, fontSize: 12, formatter: '{b}' },
      levels: [{ itemStyle: { borderColor: '#fff', borderWidth: 2, gapWidth: 2 } }],
    }],
  };

  // Dynamic insight: plain-language summary for the scatter chart
  const scatterInsight = (() => {
    if (!topQualityTopics.length || !scatterDataSource.length) return null;
    const top = topQualityTopics[0];
    const aboveAvgCount = scatterDataSource.filter(t => t.effectIndex >= 1).length;
    const belowAvgTop = [...scatterDataSource]
      .filter(t => t.size >= largeTopicThreshold && t.effectIndex < 1)
      .sort((a, b) => b.size - a.size)[0];
    const parts: string[] = [
      `垂直精准主题的获赞效率远超通用主题：「${top.displayLabel}」每千条 Prompt 获赞是平台均值的 ${formatEffectIndex(top.effectIndex)}，共 ${aboveAvgCount} 个主题超过平台平均水平。`,
    ];
    if (belowAvgTop) {
      parts.push(`而规模最大的「${belowAvgTop.displayLabel}」效率仅为均值的 ${formatEffectIndex(belowAvgTop.effectIndex)}。`);
    }
    parts.push('主题规模越大，单条获赞越少 — 建议优先引导用户创作 Logo、角色等垂直类内容。');
    return parts.join('');
  })();

  // Topic quality scatter: size vs avg_likes
  const scatterOption = {
    tooltip: {
      trigger: 'item' as const,
      confine: true,
      position: function (_point: number[], _params: unknown, _dom: unknown, _rect: unknown, size: { contentSize: number[]; viewSize: number[] }) {
        // Always position tooltip to upper-right of cursor, never overlapping the bubble
        return [_point[0] + 20, _point[1] - size.contentSize[1] - 10];
      },
      formatter: (p: { data?: { topicLabel?: string; size?: number; likesPerThousand?: number; effectIndex?: number; avgScore?: number } }) => {
        const point = p.data;
        if (!point) return '';
        return [
          point.topicLabel,
          `主题规模: ${point.size ?? 0} 条`,
          `每千条Prompt获赞: ${formatPerThousand(point.likesPerThousand ?? 0)}`,
          `效果指数: ${formatEffectIndex(point.effectIndex ?? 0)}`,
          `平均评分: ${(point.avgScore ?? 0).toFixed(2)}`,
        ].join('<br/>');
      },
    },
    grid: { left: 60, right: 40, top: 50, bottom: 40 },
    legend: { right: 0, top: 0, data: ['主题气泡', '趋势线'] },
    xAxis: { type: 'value' as const, name: '主题规模（累计生成Prompt数）', nameLocation: 'middle' as const, nameGap: 25 },
    yAxis: {
      type: 'value' as const,
      name: '千赞效率',
      nameLocation: 'middle' as const,
      nameGap: 40,
      axisLabel: { formatter: (value: number) => formatPerThousand(value) },
      splitLine: { lineStyle: { type: 'dashed' as const } },
    },
    series: [
      {
        name: '主题气泡',
        type: 'scatter',
        symbolSize: (_value: number[], params: { data?: { size?: number } }) => getBubbleSize(params.data?.size || 0),
        data: scatterPoints,
      },
      {
        name: '趋势线',
        type: 'line',
        data: regressionLineData,
        smooth: false,
        symbol: 'none',
        lineStyle: { color: '#8c8c8c', type: 'dashed' as const, width: 2 },
        tooltip: { show: false },
      },
    ],
  };

  // Quality bar chart
  const qualityBarOption = {
    tooltip: {
      trigger: 'axis' as const,
      axisPointer: { type: 'shadow' as const },
      formatter: (items: Array<{ data?: { topicLabel?: string; effectIndex?: number; likesPerThousand?: number; avgScore?: number } }>) => {
        const item = items?.[0]?.data;
        if (!item) return '';
        return [
          item.topicLabel,
          `效果指数: ${formatEffectIndex(item.effectIndex ?? 0)}`,
          `每千条Prompt获赞: ${formatPerThousand(item.likesPerThousand ?? 0)}`,
          `平均评分: ${(item.avgScore ?? 0).toFixed(2)}`,
        ].join('<br/>');
      },
    },
    grid: { left: 140, right: 40, top: 10, bottom: 20 },
    xAxis: {
      type: 'value' as const,
      name: '千赞效率（相对平台均值）',
      nameGap: 18,
      axisLabel: { formatter: (value: number) => formatEffectIndex(value) },
      splitLine: { lineStyle: { type: 'dashed' as const } },
    },
    yAxis: {
      type: 'category' as const,
      inverse: true,
      data: topQualityTopics.map(q => q.displayLabel),
      axisLabel: { width: 120, overflow: 'truncate' as const, fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: topQualityTopics.map(q => ({
        value: q.effectIndex,
        topicId: q.topic,
        topicLabel: q.displayLabel,
        effectIndex: q.effectIndex,
        likesPerThousand: q.likesPerThousand,
        avgScore: q.avg_score || 0,
        itemStyle: { color: getEffectColor(q.effectIndex, minEffectIndex, maxEffectIndex || 1) },
      })),
      barMaxWidth: 24,
      label: { show: true, position: 'right' as const, fontSize: 11, formatter: (p: { value: number }) => formatEffectIndex(p.value) },
      markLine: {
        symbol: 'none',
        lineStyle: { color: '#595959', type: 'dashed' as const, width: 2 },
        label: { formatter: '平台均值 1.0x', position: 'insideEndTop' as const },
        data: [{ xAxis: 1 }],
      },
    }],
  };

  return (
    <div>
      <Alert
        type="info"
        showIcon
        message={`主题模型：${data?.model || 'Loading...'} | 共 ${data?.n_topics || 0} 个主题${data?.sample_size ? ` | 样本 ${data.sample_size}` : ''}`}
        style={{ marginBottom: 16 }}
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <KpiCard title="主题数量" value={data?.n_topics || 0} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="最大主题规模" value={maxTopicSize} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="平均主题规模" value={topics.length ? Math.round(topics.reduce((a, t) => a + t.size, 0) / topics.length) : 0} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="模型" value={data?.model || '-'} loading={isLoading} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="主题分布树图" bordered={false}>
            <EChartsWrapper
              option={treemapOption}
              loading={isLoading}
              empty={!topics.length}
              height={450}
              onEvents={{
                click: (p: { data?: { topicId?: number; name?: string } }) => {
                  if (p?.data?.topicId != null) {
                    setSelectedTopic(p.data.topicId);
                  }
                },
              }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8} id="topic-detail-panel">
          <Card title={selected ? `${selected.keywords.slice(0, 3).join(', ')}（${selected.size} 条）` : '选择一个主题'} bordered={false}>
            {selected ? (
              <>
                <div style={{ marginBottom: 12 }}>
                  <Text strong>关键词：</Text>
                  <div style={{ marginTop: 8 }}>
                    {selected.keywords.map(kw => <Tag key={kw} color="blue" style={{ marginBottom: 4 }}>{kw}</Tag>)}
                  </div>
                </div>
                <div>
                  <Text strong>代表 Prompt：</Text>
                  <List
                    size="small"
                    dataSource={selected.representative_prompts}
                    renderItem={item => (
                      <List.Item>
                        <Paragraph ellipsis={{ rows: 2 }} style={{ fontSize: 12, margin: 0 }}>{item}</Paragraph>
                      </List.Item>
                    )}
                  />
                </div>
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary">规模: {selected.size} 条</Text>
                </div>
              </>
            ) : (
              <Text type="secondary">点击树图中的方块查看主题详情</Text>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          {scatterInsight && (
            <Alert
              type="info"
              showIcon
              description={scatterInsight}
              style={{ marginBottom: 8, lineHeight: 1.8 }}
            />
          )}
          <Card title="主题 - 效果散点图（规模 vs 点赞数）" bordered={false}
            extra={<Text type="secondary" style={{ fontSize: 12 }}>气泡大小代表主题累计生成量</Text>}>
            <EChartsWrapper
              option={scatterOption}
              loading={isLoading}
              empty={!scatterDataSource.length}
              height={420}
              onEvents={{
                click: (p: { data?: { topicId?: number } }) => {
                  if (p?.data?.topicId != null) {
                    handleTopicClick(p.data.topicId);
                    navigate(`/topic-analysis/${p.data.topicId}`);
                  }
                },
              }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="主题平均点赞排行" bordered={false}>
            <EChartsWrapper
              option={qualityBarOption}
              loading={isLoading}
              empty={!topQualityTopics.length}
              height={420}
              onEvents={{
                click: (p: { data?: { topicId?: number } }) => {
                  if (p?.data?.topicId != null) {
                    handleTopicClick(p.data.topicId);
                    navigate(`/topic-analysis/${p.data.topicId}`);
                  }
                },
              }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="主题分析洞察" bordered={false}>
            <Row gutter={24}>
              <Col xs={24} lg={8}>
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ color: '#52c41a', fontSize: 14 }}>运营重点（高效果）</Text>
                  {goldenThemes.length ? goldenThemes.map((item, idx) => (
                    <div key={idx} style={{ marginTop: 8, padding: '8px 12px', background: '#f6ffed', borderRadius: 6, fontSize: 13 }}>
                      <div><Text strong>{item.displayLabel}</Text></div>
                      <div style={{ color: '#666' }}>
                        {formatVsPlatformText(item.effectIndex)} · 千赞效率 {formatPerThousand(item.likesPerThousand)}
                      </div>
                    </div>
                  )) : <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>暂无高效果主题</Text>}
                </div>
              </Col>
              <Col xs={24} lg={8}>
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ color: '#faad14', fontSize: 14 }}>待优化（高规模低效果）</Text>
                  {optimizationThemes.filter(t => t.effectIndex < 1).length ? optimizationThemes.filter(t => t.effectIndex < 1).map((item, idx) => (
                    <div key={idx} style={{ marginTop: 8, padding: '8px 12px', background: '#fffbe6', borderRadius: 6, fontSize: 13 }}>
                      <div><Text strong>{item.displayLabel}</Text></div>
                      <div style={{ color: '#666' }}>
                        {formatVsPlatformText(item.effectIndex)} · 千赞效率 {formatPerThousand(item.likesPerThousand)}
                      </div>
                    </div>
                  )) : <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>暂无需要干预的主题</Text>}
                </div>
              </Col>
              <Col xs={24} lg={8}>
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ fontSize: 14 }}>整体趋势</Text>
                  <div style={{ marginTop: 8, padding: '8px 12px', background: '#f5f5f5', borderRadius: 6, fontSize: 13, lineHeight: 1.8 }}>
                    <div>平台平均千赞效率：<Text strong>{formatPerThousand(platformAvgLikes * 1000)}</Text></div>
                    <div>有效果主题：<Text strong>{validEffectTopics.length}</Text> / {topics.length} 个</div>
                    <div>最高效果主题：<Text strong>{topQualityTopics[0]?.displayLabel || '-'}</Text>（{formatEffectIndex(topQualityTopics[0]?.effectIndex || 0)}）</div>
                    <div style={{ marginTop: 4, color: '#1677ff' }}>
                      主题规模越大，千赞效率越低 — 垂直领域主题更容易获得高互动
                    </div>
                  </div>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TopicAnalysisPage;
