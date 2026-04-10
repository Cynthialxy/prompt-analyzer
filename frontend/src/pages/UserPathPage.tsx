import React from 'react';
import { Row, Col, Card, Table, Tag, Alert } from 'antd';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import KpiCard from '../components/common/KpiCard';
import { useUserPath } from '../hooks/useAnalysisData';

const UserPathPage: React.FC = () => {
  const { data, isLoading } = useUserPath();

  const sankey = data?.sankey || { nodes: [], links: [] };
  const patterns = data?.iteration_patterns;
  const transitions = data?.top_transitions || [];
  const entryExit = data?.category_entry_exit || [];

  // Sankey chart
  const sankeyOption = {
    tooltip: {
      trigger: 'item' as const,
      triggerOn: 'mousemove' as const,
    },
    series: [{
      type: 'sankey',
      left: 20,
      right: 160,
      top: 20,
      bottom: 20,
      data: sankey.nodes,
      links: sankey.links,
      emphasis: { focus: 'adjacency' as const },
      lineStyle: { color: 'gradient' as const, curveness: 0.5 },
      label: { fontSize: 12, width: 140, overflow: 'truncate' as const },
      nodeWidth: 20,
      nodeGap: 10,
    }],
  };

  // Category transition bar chart
  const transitionOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 200, right: 40, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...transitions].reverse().slice(0, 15).map(t => `${t.from} → ${t.to}`),
      axisLabel: { fontSize: 11, width: 180, overflow: 'truncate' as const },
    },
    series: [{
      type: 'bar',
      data: [...transitions].reverse().slice(0, 15).map(t => t.count),
      itemStyle: { color: '#722ed1', borderRadius: [0, 4, 4, 0] },
      barMaxWidth: 20,
      label: { show: true, position: 'right' as const, fontSize: 11 },
    }],
  };

  return (
    <div>
      <Alert
        type="info"
        showIcon
        message="基于用户 prompt 时间序列挖掘创作路径：初始描述 → 风格细化 → 最终生成"
        style={{ marginBottom: 16 }}
      />

      {patterns && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <KpiCard title="分析用户数" value={patterns.users_analyzed} loading={isLoading} />
          </Col>
          <Col xs={12} sm={6}>
            <KpiCard title="人均 Prompt 数" value={patterns.avg_prompts_per_user} loading={isLoading} />
          </Col>
          <Col xs={12} sm={6}>
            <KpiCard
              title="平均长度增长率"
              value={`${(patterns.avg_length_growth * 100).toFixed(1)}%`}
              loading={isLoading}
            />
          </Col>
          <Col xs={12} sm={6}>
            <KpiCard title="迭代精细化用户" value={patterns.users_with_growth} loading={isLoading} />
          </Col>
        </Row>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card title="创作路径桑基图（类别 → 风格）" bordered={false}>
            <EChartsWrapper
              option={sankeyOption}
              loading={isLoading}
              empty={!sankey.links.length}
              height={500}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Top 类别迁移路径" bordered={false}>
            <EChartsWrapper
              option={transitionOption}
              loading={isLoading}
              empty={!transitions.length}
              height={400}
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="类别进出统计" bordered={false}>
            <Table
              dataSource={entryExit}
              rowKey="category"
              size="small"
              pagination={false}
              scroll={{ y: 400 }}
              columns={[
                { title: '类别', dataIndex: 'category', key: 'cat', render: (v: string) => <Tag color="blue">{v}</Tag> },
                { title: '流入', dataIndex: 'in', key: 'in', sorter: (a: { in: number }, b: { in: number }) => a.in - b.in },
                { title: '流出', dataIndex: 'out', key: 'out', sorter: (a: { out: number }, b: { out: number }) => a.out - b.out },
                { title: '停留', dataIndex: 'stay', key: 'stay' },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default UserPathPage;
