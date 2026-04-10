import React, { useState } from 'react';
import { Row, Col, Card, Select } from 'antd';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useCategories } from '../hooks/useAnalysisData';

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911'];

const COLOR_MAP: Record<string, string> = {
  'red': '#ff4d4f', 'blue': '#1677ff', 'green': '#52c41a', 'yellow': '#fadb14',
  'orange': '#fa8c16', 'purple': '#722ed1', 'pink': '#eb2f96', 'brown': '#8B4513',
  'black': '#333', 'white': '#d9d9d9', 'grey': '#8c8c8c', 'gray': '#8c8c8c',
  'gold': '#d4af37', 'silver': '#c0c0c0', 'beige': '#f5f5dc', 'teal': '#13c2c2',
  'tan': '#d2b48c', 'peach': '#ffdab9', 'cream': '#fffdd0',
};

const CategoryPage: React.FC = () => {
  const { data: categories, isLoading } = useCategories();
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const filteredStyles = selectedCategory
    ? (categories?.category_style_cross || [])
        .filter(c => c.llm_category === selectedCategory)
        .map(c => ({ name: c.llm_style, count: c.count }))
    : categories?.llm_style || [];

  // Category bar chart
  const categoryOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 140, right: 40, top: 20, bottom: 30 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...(categories?.llm_category || [])].reverse().map(c => c.name),
      axisLabel: { width: 120, overflow: 'truncate' as const },
    },
    series: [{
      type: 'bar',
      data: [...(categories?.llm_category || [])].reverse().map((c, i) => ({
        value: c.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 30,
    }],
  };

  // Style pie
  const styleOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'horizontal' as const, bottom: 0, left: 'center', type: 'scroll' as const },
    series: [{
      type: 'pie',
      radius: ['30%', '55%'],
      center: ['50%', '45%'],
      label: { show: true, formatter: '{b}\n{d}%', fontSize: 11 },
      labelLine: { length: 10, length2: 8 },
      data: (filteredStyles || []).slice(0, 10).map((s, i) => ({
        name: s.name,
        value: s.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  };

  // Use case stacked bar
  const useCaseOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 120, right: 40, top: 20, bottom: 30 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...(categories?.llm_use_case || [])].reverse().map(c => c.name),
      axisLabel: { width: 100, overflow: 'truncate' as const },
    },
    series: [{
      type: 'bar',
      data: [...(categories?.llm_use_case || [])].reverse().map((c, i) => ({
        value: c.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 30,
    }],
  };

  // Color visualization
  const colorOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c}' },
    grid: { left: 80, right: 20, top: 10, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: (categories?.llm_color || []).slice(0, 20).map(c => c.name),
      axisLabel: { rotate: 45, fontSize: 10 },
    },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'bar',
      data: (categories?.llm_color || []).slice(0, 20).map(c => ({
        value: c.count,
        itemStyle: { color: COLOR_MAP[c.name] || '#8c8c8c' },
      })),
    }],
  };

  // Heatmap: category x style
  const catNames = [...new Set((categories?.category_style_cross || []).map(c => c.llm_category))].slice(0, 10);
  const styleNames = [...new Set((categories?.category_style_cross || []).map(c => c.llm_style))].slice(0, 8);
  const heatmapData = (categories?.category_style_cross || [])
    .filter(c => catNames.includes(c.llm_category) && styleNames.includes(c.llm_style))
    .map(c => [catNames.indexOf(c.llm_category), styleNames.indexOf(c.llm_style), c.count]);

  const heatmapOption = {
    tooltip: { formatter: (p: { data: number[] }) => `${catNames[p.data[0]]} x ${styleNames[p.data[1]]}: ${p.data[2]}` },
    grid: { left: 140, right: 80, top: 10, bottom: 80 },
    xAxis: { type: 'category' as const, data: catNames, axisLabel: { rotate: 45, fontSize: 10 } },
    yAxis: { type: 'category' as const, data: styleNames },
    visualMap: { min: 0, max: Math.max(...heatmapData.map(d => d[2]), 1), orient: 'vertical' as const, right: 10, top: 'center', inRange: { color: ['#e6f4ff', '#1677ff'] } },
    series: [{
      type: 'heatmap',
      data: heatmapData,
      label: { show: true, fontSize: 10 },
    }],
  };

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col span={24}>
          <Card bordered={false}>
            <span style={{ marginRight: 12 }}>按类别筛选：</span>
            <Select
              allowClear
              placeholder="全部类别"
              style={{ width: 240 }}
              value={selectedCategory}
              onChange={setSelectedCategory}
              options={(categories?.llm_category || []).map(c => ({
                label: `${c.name} (${c.count})`,
                value: c.name,
              }))}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="类别分布" bordered={false}>
            <EChartsWrapper option={categoryOption} loading={isLoading} empty={!categories?.llm_category?.length} height={400} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title={selectedCategory ? `${selectedCategory} 的风格分布` : '风格分布'} bordered={false}>
            <EChartsWrapper option={styleOption} loading={isLoading} empty={!filteredStyles?.length} height={400} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="用途分布" bordered={false}>
            <EChartsWrapper option={useCaseOption} loading={isLoading} empty={!categories?.llm_use_case?.length} height={350} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="颜色分布" bordered={false}>
            <EChartsWrapper option={colorOption} loading={isLoading} empty={!categories?.llm_color?.length} height={350} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col span={24}>
          <Card title="类别 × 风格热力图" bordered={false}>
            <EChartsWrapper option={heatmapOption} loading={isLoading} empty={!heatmapData.length} height={400} />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default CategoryPage;
