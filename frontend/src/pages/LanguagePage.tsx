import React from 'react';
import { Row, Col, Card, Statistic } from 'antd';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useLanguage } from '../hooks/useAnalysisData';

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911'];

const LanguagePage: React.FC = () => {
  const { data, isLoading } = useLanguage();

  const langDist = data?.language?.distribution || [];
  const textStats = data?.text_stats;
  const quality = data?.quality;

  // Language pie
  const langPieOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical' as const, right: 10, top: 'center' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      data: langDist.slice(0, 10).map((l, i) => ({
        name: l.language, value: l.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  };

  // Language bar
  const langBarOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 60, right: 20, top: 10, bottom: 60 },
    xAxis: {
      type: 'category' as const,
      data: langDist.slice(0, 15).map(l => l.language),
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: { type: 'value' as const },
    series: [{
      type: 'bar',
      data: langDist.slice(0, 15).map((l, i) => ({
        value: l.count,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  };

  // Length histogram
  const lengthOption = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 60, right: 40, top: 40, bottom: 30 },
    xAxis: {
      type: 'category' as const,
      data: (textStats?.length_histogram || []).map(h => h.range),
      name: '字符数',
    },
    yAxis: { type: 'value' as const, name: '数量' },
    series: [{
      type: 'bar',
      data: (textStats?.length_histogram || []).map(h => h.count),
      itemStyle: { color: '#1677ff', borderRadius: [4, 4, 0, 0] },
    }],
    markLine: textStats ? {
      data: [
        { xAxis: 'mean', label: { formatter: `均值：${textStats.char_count.mean}` } },
      ],
    } : undefined,
  };

  // Quality distribution (if available)
  const qualityDims = ['specificity', 'clarity', 'creativity', 'technical_detail'];
  const qualityDimLabels: Record<string, string> = {
    specificity: '具体性',
    clarity: '清晰度',
    creativity: '创造力',
    technical_detail: '技术细节',
  };
  const hasQualityData = quality?.summary && qualityDims.some(d => quality.summary[d]?.mean > 0);

  const qualityRadarOption = hasQualityData ? {
    radar: {
      indicator: qualityDims.map(d => ({ name: qualityDimLabels[d] || d, max: 5 })),
    },
    series: [{
      type: 'radar',
      data: [{
        value: qualityDims.map(d => quality.summary[d]?.mean || 0),
        name: '平均质量',
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#1677ff' },
      }],
    }],
  } : null;

  const qualityBarOption = hasQualityData ? {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 120, right: 20, top: 10, bottom: 30 },
    xAxis: { type: 'value' as const, max: 5 },
    yAxis: {
      type: 'category' as const,
      data: qualityDims.map(d => qualityDimLabels[d] || d),
    },
    series: [{
      type: 'bar',
      data: qualityDims.map((d, i) => ({
        value: quality.summary[d]?.mean || 0,
        itemStyle: { color: COLORS[i] },
      })),
      barMaxWidth: 30,
    }],
  } : null;

  return (
    <div>
      {/* Stats cards */}
      {textStats && (
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <Card bordered={false}>
              <Statistic title="平均字符数" value={textStats.char_count.mean} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card bordered={false}>
              <Statistic title="中位数字符数" value={textStats.char_count.median} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card bordered={false}>
              <Statistic title="P95 字符数" value={textStats.char_count.p95} />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card bordered={false}>
              <Statistic title="词汇多样性" value={textStats.lexical_diversity.mean} precision={3} />
            </Card>
          </Col>
        </Row>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card title="语言分布" bordered={false}>
            <EChartsWrapper option={langPieOption} loading={isLoading} empty={!langDist.length} height={360} />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="各语言数量" bordered={false}>
            <EChartsWrapper option={langBarOption} loading={isLoading} empty={!langDist.length} height={360} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="Prompt 长度分布" bordered={false}>
            <EChartsWrapper
              option={lengthOption}
              loading={isLoading}
              empty={!textStats?.length_histogram?.length}
              height={350}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="Prompt 质量雷达图" bordered={false}>
            {qualityRadarOption ? (
              <EChartsWrapper option={qualityRadarOption} height={350} />
            ) : (
              <EChartsWrapper option={{}} empty height={350} />
            )}
          </Card>
        </Col>
      </Row>

      {qualityBarOption && (
        <Row gutter={[16, 16]}>
          <Col span={24}>
            <Card
              title={`质量评分（采样：${quality?.sample_size || 0} 条）`}
              bordered={false}
            >
              <EChartsWrapper option={qualityBarOption} height={250} />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
};

export default LanguagePage;
