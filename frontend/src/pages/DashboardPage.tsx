import React, { useState } from 'react';
import { Row, Col, Card, Alert, DatePicker } from 'antd';
import {
  FileTextOutlined,
  TeamOutlined,
  FieldStringOutlined,
  TagOutlined,
} from '@ant-design/icons';
import type { Dayjs } from 'dayjs';
import KpiCard from '../components/common/KpiCard';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useSummary, useCategories, useDailyCounts, useLanguage, useThemeSummary } from '../hooks/useAnalysisData';

const { RangePicker } = DatePicker;

/** Format date string like '20260109' to '2026-01-09', or pass through if already formatted */
function formatDate(d: string): string {
  if (!d) return '';
  if (d.length === 8 && !d.includes('-')) {
    return `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
  }
  return d;
}

const DashboardPage: React.FC = () => {
  const [dateRange, setDateRange] = useState<{ date_from?: string; date_to?: string }>({});

  const { data: summary, isLoading: summaryLoading } = useSummary(dateRange);
  const { data: categories, isLoading: catLoading } = useCategories();
  const { data: dailyCounts } = useDailyCounts(dateRange);
  const { data: langData } = useLanguage();
  const { data: theme } = useThemeSummary();

  const handleDateChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    if (dates && dates[0] && dates[1]) {
      setDateRange({
        date_from: dates[0].format('YYYY-MM-DD'),
        date_to: dates[1].format('YYYY-MM-DD'),
      });
    } else {
      setDateRange({});
    }
  };

  const topCategory = summary?.top_categories?.[0]?.name || '-';

  // Category bar chart
  const categoryOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 160, right: 40, top: 20, bottom: 30 },
    xAxis: { type: 'value' as const },
    yAxis: {
      type: 'category' as const,
      data: [...(categories?.llm_category || [])].reverse().slice(0, 10).map(c => c.name),
      axisLabel: { width: 140, overflow: 'break' as const, fontSize: 12 },
    },
    series: [{
      type: 'bar',
      data: [...(categories?.llm_category || [])].reverse().slice(0, 10).map(c => c.count),
      itemStyle: { color: '#1677ff', borderRadius: [0, 4, 4, 0] },
    }],
  };

  // Style pie chart
  const styleOption = {
    tooltip: { trigger: 'item' as const },
    legend: { orient: 'vertical' as const, right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      label: { show: false },
      data: (categories?.llm_style || []).slice(0, 8).map(s => ({
        name: s.name,
        value: s.count,
      })),
    }],
  };

  // Daily volume chart
  const dailyData = (dailyCounts || []).map(d => ({
    date: formatDate(d.date),
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

  // Language donut
  const langOption = {
    tooltip: { trigger: 'item' as const },
    legend: { orient: 'vertical' as const, right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['45%', '70%'],
      label: { show: false },
      data: (langData?.language?.distribution || []).slice(0, 8).map(l => ({
        name: l.language,
        value: l.count,
      })),
    }],
  };

  return (
    <div>
      {/* Theme Summary */}
      {theme?.text && !theme.text.toLowerCase().includes('unavailable') && !theme.text.toLowerCase().includes('no theme summary') && (
        <Alert
          message="AI 洞察"
          description={<div style={{ whiteSpace: 'pre-wrap' }}>{theme.text}</div>}
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />
      )}

      {/* Date Filter */}
      <Card bordered={false} style={{ marginBottom: 16 }}>
        <span style={{ marginRight: 12 }}>时间范围：</span>
        <RangePicker
          onChange={handleDateChange}
          allowClear
          placeholder={['开始日期', '结束日期']}
        />
        {dateRange.date_from && (
          <span style={{ marginLeft: 12, color: '#666', fontSize: 13 }}>
            {dateRange.date_from} ~ {dateRange.date_to}
          </span>
        )}
      </Card>

      {/* KPI Cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <KpiCard
            title="总 Prompt 数"
            value={summary?.total_prompts || 0}
            prefix={<FileTextOutlined />}
            loading={summaryLoading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard
            title="独立用户数"
            value={summary?.unique_users || 0}
            prefix={<TeamOutlined />}
            loading={summaryLoading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard
            title="平均 Prompt 长度"
            value={summary?.avg_prompt_length || 0}
            suffix="字符"
            prefix={<FieldStringOutlined />}
            loading={summaryLoading}
          />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard
            title="热门类别"
            value={topCategory}
            prefix={<TagOutlined />}
            loading={summaryLoading}
          />
        </Col>
      </Row>

      {/* Charts */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={14}>
          <Card title="类别分布（前 10）" bordered={false}>
            <EChartsWrapper
              option={categoryOption}
              loading={catLoading}
              empty={!categories?.llm_category?.length}
              height={360}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="风格分布" bordered={false}>
            <EChartsWrapper
              option={styleOption}
              loading={catLoading}
              empty={!categories?.llm_style?.length}
              height={360}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="每日 Prompt 量" bordered={false}>
            <EChartsWrapper
              option={dailyOption}
              empty={!dailyCounts?.length}
              height={300}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="语言分布" bordered={false}>
            <EChartsWrapper
              option={langOption}
              empty={!langData?.language?.distribution?.length}
              height={300}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;
