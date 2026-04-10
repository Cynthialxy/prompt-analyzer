import React, { useState } from 'react';
import { Row, Col, Card, Tag, List, Typography } from 'antd';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useTopics } from '../hooks/useAnalysisData';

const { Text, Paragraph } = Typography;

const CLUSTER_COLORS = [
  '#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911',
  '#36cfc9', '#ffc53d', '#ff7a45', '#9254de', '#73d13d',
];

/** Generate a readable label: "主题 1：hair, character, anime" */
function clusterLabel(c: { label: string; id?: number; keywords: string[] }): string {
  const num = c.id != null ? c.id + 1 : c.label.replace(/\D/g, '');
  const kws = c.keywords.slice(0, 3).join(', ');
  return `主题 ${num}：${kws}`;
}

/** Short label for charts: "主题1: hair, character" */
function shortLabel(c: { id: number; keywords: string[] }): string {
  return `主题${c.id + 1}: ${c.keywords.slice(0, 2).join(', ')}`;
}

const TopicPage: React.FC = () => {
  const { data: topics, isLoading } = useTopics();
  const [selectedCluster, setSelectedCluster] = useState<number | null>(null);

  const cluster = selectedCluster !== null
    ? topics?.clusters?.find(c => c.id === selectedCluster)
    : null;

  // Scatter plot
  const scatterOption = {
    tooltip: {
      confine: true,
      extraCssText: 'max-width: 360px; white-space: normal; word-break: break-word; line-height: 1.5;',
      formatter: (p: { data: number[] }) => {
        const point = topics?.scatter_data?.[p.data[3]];
        if (!point) return '';
        const c = topics?.clusters?.find(cl => cl.id === point.topic_id);
        const label = c ? `主题 ${c.id + 1}：${c.keywords.slice(0, 3).join(', ')}` : `主题 ${point.topic_id + 1}`;
        return `<b>${label}</b><br/><span style="color:#666">${point.prompt_preview}</span>`;
      },
    },
    grid: { left: 50, right: 20, top: 30, bottom: 50 },
    xAxis: { type: 'value' as const, name: 't-SNE 维度 1', nameLocation: 'middle' as const, nameGap: 25, axisLabel: { show: false } },
    yAxis: { type: 'value' as const, name: 't-SNE 维度 2', nameLocation: 'middle' as const, nameGap: 35, axisLabel: { show: false } },
    series: (topics?.clusters || []).map((c) => ({
      type: 'scatter',
      name: c.label,
      symbolSize: 6,
      data: (topics?.scatter_data || [])
        .map((p, idx) => p.topic_id === c.id ? [p.x, p.y, c.id, idx] : null)
        .filter(Boolean),
      itemStyle: { color: CLUSTER_COLORS[c.id % CLUSTER_COLORS.length], opacity: 0.7 },
    })),
    legend: { show: false },
  };

  // Cluster size bar chart
  const sizeOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 160, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...(topics?.clusters || [])].sort((a, b) => a.size - b.size).map(c => shortLabel(c)),
      axisLabel: { width: 140, overflow: 'truncate' as const, fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: [...(topics?.clusters || [])].sort((a, b) => a.size - b.size).map(c => ({
        value: c.size,
        itemStyle: { color: CLUSTER_COLORS[c.id % CLUSTER_COLORS.length] },
      })),
      barMaxWidth: 24,
    }],
  };

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={16}>
          <Card title="主题聚类（t-SNE 投影）" bordered={false}>
            <EChartsWrapper
              option={scatterOption}
              loading={isLoading}
              empty={!topics?.scatter_data?.length}
              height={500}
              onEvents={{
                click: (params: { data?: number[] }) => {
                  if (params.data && params.data.length >= 3) {
                    setSelectedCluster(params.data[2]);
                  }
                },
              }}
            />
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card
            title={cluster ? `${clusterLabel(cluster)}（${cluster.size} 条）` : '选择一个聚类'}
            bordered={false}
            style={{ height: '100%' }}
          >
            {cluster ? (
              <>
                <div style={{ marginBottom: 16 }}>
                  <Text strong>核心关键词：</Text>
                  <div style={{ marginTop: 8 }}>
                    {cluster.keywords.map(kw => (
                      <Tag key={kw} color="blue" style={{ marginBottom: 4 }}>{kw}</Tag>
                    ))}
                  </div>
                </div>
                <div>
                  <Text strong>示例 Prompt：</Text>
                  <List
                    size="small"
                    dataSource={cluster.representative_prompts}
                    renderItem={item => (
                      <List.Item>
                        <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0, fontSize: 12 }}>
                          {item}
                        </Paragraph>
                      </List.Item>
                    )}
                  />
                </div>
              </>
            ) : (
              <Text type="secondary">点击散点图中的点查看聚类详情</Text>
            )}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="聚类规模" bordered={false}>
            <EChartsWrapper
              option={sizeOption}
              loading={isLoading}
              empty={!topics?.clusters?.length}
              height={400}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="全部聚类" bordered={false}>
            <List
              size="small"
              dataSource={[...(topics?.clusters || [])].sort((a, b) => b.size - a.size)}
              renderItem={c => (
                <List.Item
                  onClick={() => setSelectedCluster(c.id)}
                  style={{ cursor: 'pointer', background: selectedCluster === c.id ? '#e6f4ff' : 'transparent', padding: '8px 12px', borderRadius: 6 }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
                    <div style={{
                      width: 12, height: 12, borderRadius: '50%',
                      background: CLUSTER_COLORS[c.id % CLUSTER_COLORS.length],
                      flexShrink: 0,
                    }} />
                    <Text strong style={{ minWidth: 70 }}>{shortLabel(c)}</Text>
                    <Text type="secondary" style={{ flex: 1 }}>
                      {c.keywords.slice(0, 5).join(', ')}
                    </Text>
                    <Tag>{c.size}</Tag>
                  </div>
                </List.Item>
              )}
              style={{ maxHeight: 380, overflow: 'auto' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TopicPage;
