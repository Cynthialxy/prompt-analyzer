import React from 'react';
import { Row, Col, Card, Alert, Typography, Statistic } from 'antd';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import KpiCard from '../components/common/KpiCard';
import { useRetention } from '../hooks/useAnalysisData';

const { Text } = Typography;

const UserRetentionPage: React.FC = () => {
  const { data, isLoading } = useRetention();

  const cohorts = data?.cohorts || [];
  const overall = data?.overall || {};
  const regen = data?.re_generation;

  // Checkpoints (D0, D1, D3, D7, D14, D30)
  const checkpoints = [0, 1, 3, 7, 14, 30];

  // Build heatmap data
  const heatmapData: [number, number, number][] = [];
  cohorts.forEach((cohort, i) => {
    checkpoints.forEach((cp, j) => {
      const rate = cohort.retention_rate[String(cp)] || (cp === 0 ? 1 : 0);
      heatmapData.push([j, cohorts.length - 1 - i, Math.round(rate * 10000) / 100]);
    });
  });

  const heatmapOption = {
    tooltip: {
      position: 'top',
      formatter: (p: { data: number[] }) => {
        const cohort = cohorts[cohorts.length - 1 - p.data[1]];
        const day = checkpoints[p.data[0]];
        return `${cohort?.cohort}<br/>D${day}: ${p.data[2]}%`;
      },
    },
    grid: { left: 100, right: 60, top: 30, bottom: 20 },
    xAxis: {
      type: 'category' as const,
      data: checkpoints.map(c => `D${c}`),
      position: 'top' as const,
      splitArea: { show: true },
    },
    yAxis: {
      type: 'category' as const,
      data: [...cohorts].reverse().map(c => c.cohort),
      splitArea: { show: true },
    },
    visualMap: {
      min: 0, max: 100,
      orient: 'vertical' as const,
      right: 10, top: 'center' as const,
      inRange: { color: ['#fff', '#1677ff'] },
      formatter: (v: number) => `${v}%`,
    },
    series: [{
      type: 'heatmap',
      data: heatmapData,
      label: { show: true, formatter: (p: { data: number[] }) => p.data[2] > 0 ? `${p.data[2]}%` : '-', fontSize: 10 },
    }],
  };

  // Overall retention line chart
  const lineOption = {
    tooltip: { trigger: 'axis' as const, formatter: (p: { name: string; value: number }[]) => `${p[0].name}<br/>留存率: ${(p[0].value * 100).toFixed(2)}%` },
    grid: { left: 60, right: 40, top: 20, bottom: 40 },
    xAxis: {
      type: 'category' as const,
      data: ['D1', 'D3', 'D7', 'D14', 'D30'],
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` },
    },
    series: [{
      type: 'line',
      data: [overall.d1 || 0, overall.d3 || 0, overall.d7 || 0, overall.d14 || 0, overall.d30 || 0],
      smooth: true,
      itemStyle: { color: '#1677ff' },
      areaStyle: { opacity: 0.3 },
      label: { show: true, formatter: (p: { value: number }) => `${(p.value * 100).toFixed(1)}%` },
    }],
  };

  // Re-generation distribution
  const regenOption = regen ? {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['50%', '45%'],
      data: [
        { name: '单日用户', value: regen.single_day, itemStyle: { color: '#ff4d4f' } },
        { name: '少量活跃(2-5天)', value: regen.few_days, itemStyle: { color: '#faad14' } },
        { name: '频繁活跃(6-14天)', value: regen.frequent, itemStyle: { color: '#1677ff' } },
        { name: '重度用户(>14天)', value: regen.heavy, itemStyle: { color: '#52c41a' } },
      ],
    }],
  } : null;

  return (
    <div>
      {data?.window_days && (
        <Alert
          type="info"
          showIcon
          message={`分析窗口：最近 ${data.window_days} 天 | 复生成率：${regen?.rate ? (regen.rate * 100).toFixed(1) : 0}% | 平均活跃间隔：${data.avg_active_interval_days} 天`}
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <KpiCard title="7日留存率" value={overall.d7 ? `${(overall.d7 * 100).toFixed(1)}%` : '-'} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="30日留存率" value={overall.d30 ? `${(overall.d30 * 100).toFixed(1)}%` : '-'} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="复生成率" value={regen?.rate ? `${(regen.rate * 100).toFixed(1)}%` : '-'} loading={isLoading} />
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="平均活跃间隔" value={data?.avg_active_interval_days || 0} suffix="天" loading={isLoading} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="Cohort 同期群留存矩阵" bordered={false}>
            <EChartsWrapper option={heatmapOption} loading={isLoading} empty={!cohorts.length} height={Math.max(400, cohorts.length * 22)} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="整体留存曲线" bordered={false}>
            <EChartsWrapper option={lineOption} loading={isLoading} empty={!overall.d7} height={300} />
          </Card>
          {regenOption && (
            <Card title="用户复生成分布" bordered={false} style={{ marginTop: 16 }}>
              <EChartsWrapper option={regenOption} loading={isLoading} height={280} />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default UserRetentionPage;
