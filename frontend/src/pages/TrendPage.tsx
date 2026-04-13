import React, { useEffect, useRef } from 'react';
import { Row, Col, Card, Table, Tag } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useTrends } from '../hooks/useAnalysisData';
import * as echarts from 'echarts';
import 'echarts-wordcloud';

function formatDate(d: string): string {
  if (!d) return '';
  if (d.length === 8 && !d.includes('-')) {
    return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
  }
  return d;
}

const TrendPage: React.FC = () => {
  const { data: trends, isLoading } = useTrends();
  const wordCloudRef = useRef<HTMLDivElement>(null);

  // Daily volume chart
  const dailyData = (trends?.daily_counts || []).map((d: Record<string, any>) => ({
    date: formatDate(d.pt || d.date),
    count: d.count,
  }));
  const dailyOption = {
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: { name: string; value: number }[]) => {
        const p = params[0];
        return `${p.name}<br/>Prompt 数量：<b>${p.value.toLocaleString()}</b>`;
      },
    },
    grid: { left: 70, right: 40, top: 20, bottom: 40 },
    xAxis: {
      type: 'category' as const,
      data: dailyData.map(d => d.date),
      axisLabel: { fontSize: 11 },
    },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'line',
      data: dailyData.map(d => d.count),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color: '#1677ff' },
      lineStyle: { color: '#1677ff', width: 2 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(22,119,255,0.3)' },
            { offset: 1, color: 'rgba(22,119,255,0.02)' },
          ],
        },
      },
      label: {
        show: true,
        position: 'top' as const,
        formatter: (p: { value: number }) => p.value.toLocaleString(),
        fontSize: 11,
      },
    }],
  };

  // Category trends (top 5 categories)
  const catMap = new Map<string, { dates: string[]; counts: number[] }>();
  for (const item of trends?.category_trends || []) {
    if (!catMap.has(item.llm_category)) {
      catMap.set(item.llm_category, { dates: [], counts: [] });
    }
    const entry = catMap.get(item.llm_category)!;
    entry.dates.push(formatDate(item.pt));
    entry.counts.push(item.count);
  }
  const topCats = [...catMap.entries()]
    .map(([name, data]) => ({ name, total: data.counts.reduce((a, b) => a + b, 0), data }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 5);

  const allDates = [...new Set((trends?.category_trends || []).map(c => formatDate(c.pt)))].sort();
  const catTrendOption = {
    tooltip: { trigger: 'axis' as const },
    legend: { data: topCats.map(c => c.name), bottom: 0 },
    grid: { left: 60, right: 40, top: 20, bottom: 70 },
    xAxis: { type: 'category' as const, data: allDates, axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value' as const },
    series: topCats.map(cat => {
      const dateCountMap = new Map(cat.data.dates.map((d, i) => [d, cat.data.counts[i]]));
      return {
        name: cat.name,
        type: 'line',
        smooth: true,
        data: allDates.map(d => dateCountMap.get(d) || 0),
      };
    }),
  };

  // Word cloud
  useEffect(() => {
    if (!wordCloudRef.current || !trends?.word_cloud?.length) return;
    const chart = echarts.init(wordCloudRef.current);
    chart.setOption({
      series: [{
        type: 'wordCloud',
        shape: 'circle',
        sizeRange: [14, 60],
        rotationRange: [-45, 45],
        rotationStep: 15,
        gridSize: 8,
        textStyle: {
          fontFamily: 'sans-serif',
          fontWeight: 'bold',
          color: () => {
            const colors = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1', '#13c2c2', '#eb2f96'];
            return colors[Math.floor(Math.random() * colors.length)];
          },
        },
        data: trends.word_cloud.slice(0, 80),
      }],
    });
    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.dispose();
    };
  }, [trends?.word_cloud]);

  // Trending keywords table
  type KeywordRow = { keyword: string; recent_count: number; previous_count: number; direction: string; momentum: number };
  const keywordColumns: import('antd').TableColumnsType<KeywordRow> = [
    {
      title: '关键词',
      dataIndex: 'keyword',
      key: 'keyword',
      render: (text: string) => <Tag>{text}</Tag>,
    },
    {
      title: '近期',
      dataIndex: 'recent_count',
      key: 'recent_count',
      sorter: (a: { recent_count: number }, b: { recent_count: number }) => a.recent_count - b.recent_count,
    },
    {
      title: '之前',
      dataIndex: 'previous_count',
      key: 'previous_count',
    },
    {
      title: '趋势',
      dataIndex: 'direction',
      key: 'direction',
      render: (dir: string, record: { momentum: number }) => {
        const icon = dir === 'up' ? <ArrowUpOutlined style={{ color: '#52c41a' }} />
          : dir === 'down' ? <ArrowDownOutlined style={{ color: '#ff4d4f' }} />
          : <MinusOutlined style={{ color: '#8c8c8c' }} />;
        return <span>{icon} {(record.momentum * 100).toFixed(0)}%</span>;
      },
    },
  ];

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card title="每日 Prompt 量" bordered={false}>
            <EChartsWrapper option={dailyOption} loading={isLoading} empty={!trends?.daily_counts?.length} height={300} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="类别趋势（前 5）" bordered={false}>
            <EChartsWrapper option={catTrendOption} loading={isLoading} empty={!topCats.length} height={380} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="词云" bordered={false}>
            <div ref={wordCloudRef} style={{ height: 350, width: '100%' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card title="热门关键词" bordered={false}>
            <Table
              columns={keywordColumns}
              dataSource={(trends?.trending_keywords || []).map((k, i) => ({ ...k, key: i }))}
              pagination={{ pageSize: 20 }}
              size="small"
              loading={isLoading}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default TrendPage;
