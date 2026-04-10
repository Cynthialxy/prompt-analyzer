import React, { useState, useMemo } from 'react';
import { Row, Col, Card, Tag, Typography, Button, Empty, List, Alert, Input, Select, message, Spin } from 'antd';
import { CopyOutlined, LikeOutlined, StarOutlined, SearchOutlined, TrophyOutlined, BulbOutlined } from '@ant-design/icons';
import KpiCard from '../components/common/KpiCard';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { useHotTemplates } from '../hooks/useAnalysisData';
import type { PromptTemplate } from '../types';

const { Text, Paragraph } = Typography;

const COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#722ed1',
  '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911'];

const TemplateMarketPage: React.FC = () => {
  const { data, isLoading } = useHotTemplates();
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [sortBy, setSortBy] = useState<'avg_likes' | 'usage_count' | 'avg_score'>('avg_likes');

  const templates = data?.templates || [];
  const threshold = data?.hit_threshold;
  const totalHits = data?.total_hits || 0;
  const coveredCategories = useMemo(
    () => Array.from(new Set(templates.map(t => t.category))),
    [templates]
  );

  // Filter + sort
  const filteredTemplates = useMemo(() => {
    let list = [...templates];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(t =>
        t.template_prompt.toLowerCase().includes(q) ||
        t.category?.toLowerCase().includes(q) ||
        t.style?.toLowerCase().includes(q)
      );
    }
    if (categoryFilter) {
      list = list.filter(t => t.category === categoryFilter);
    }
    list.sort((a, b) => (b[sortBy] as number) - (a[sortBy] as number));
    return list;
  }, [templates, search, categoryFilter, sortBy]);

  // Top 5 bar chart
  const top5 = [...templates].sort((a, b) => b.avg_likes - a.avg_likes).slice(0, 5);
  const top5Option = {
    tooltip: { trigger: 'axis' as const },
    grid: { left: 160, right: 40, top: 10, bottom: 20 },
    xAxis: { type: 'value' as const, name: '平均点赞' },
    yAxis: {
      type: 'category' as const,
      inverse: true,
      data: top5.map(t => `${t.category} / ${t.style}`),
      axisLabel: { width: 140, overflow: 'truncate' as const, fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: top5.map((t, i) => ({
        value: t.avg_likes,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
      barMaxWidth: 24,
      label: { show: true, position: 'right' as const, fontSize: 11 },
    }],
  };

  // Category distribution pie
  const catCounts: Record<string, number> = {};
  templates.forEach(t => { catCounts[t.category] = (catCounts[t.category] || 0) + 1; });
  const catDistOption = {
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c} ({d}%)' },
    legend: {
      orient: 'horizontal' as const,
      bottom: 0,
      left: 'center' as const,
      type: 'scroll' as const,
      itemWidth: 12,
      itemHeight: 12,
      textStyle: { fontSize: 11 },
    },
    series: [{
      type: 'pie',
      radius: ['35%', '60%'],
      center: ['50%', '42%'],
      avoidLabelOverlap: true,
      label: {
        show: true,
        formatter: '{b}\n{d}%',
        fontSize: 11,
      },
      labelLine: { length: 10, length2: 10 },
      data: Object.entries(catCounts).map(([name, value], i) => ({
        name, value,
        itemStyle: { color: COLORS[i % COLORS.length] },
      })),
    }],
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success('✅ 模板已复制到剪贴板');
  };

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" tip="正在挖掘爆款模板..." />
      </div>
    );
  }

  // Empty state
  if (templates.length === 0) {
    return (
      <div>
        <Alert
          type="info"
          showIcon
          icon={<BulbOutlined />}
          message="✨ 爆款模板挖掘中"
          description={
            <div>
              <div style={{ marginTop: 8, lineHeight: 1.8 }}>
                <div>① 点击右上角「<b>运行分析</b>」，自动从高效果 Prompt 中提取可复用模板</div>
                <div>② 分析完成后，即可查看结构化模板、使用指南和效果数据</div>
                <div>③ 一键复制模板，直接复用爆款 Prompt 逻辑</div>
              </div>
              <div style={{ marginTop: 12, color: '#666', fontSize: 12 }}>
                💡 模板提取逻辑：基于高点赞 Prompt 的句式、结构、关键词，自动生成可复用的通用模板
              </div>
            </div>
          }
          style={{ marginBottom: 16 }}
        />
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={12} sm={6}>
            <KpiCard title="模板数量" value={0} />
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
              已成功提取的可复用爆款模板数
            </Text>
          </Col>
          <Col xs={12} sm={6}>
            <KpiCard title="高效果 Prompt" value={totalHits} />
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
              符合点赞阈值的优质 Prompt 样本量
            </Text>
          </Col>
          <Col xs={12} sm={6}>
            <KpiCard title="效果阈值" value={threshold?.value ?? '-'} />
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
              当前爆款判定标准（like_count）
            </Text>
          </Col>
          <Col xs={12} sm={6}>
            <KpiCard title="覆盖类别" value={0} />
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
              模板覆盖的业务分类数
            </Text>
          </Col>
        </Row>
        <Card bordered={false}>
          <Empty
            description={
              <div>
                <div style={{ fontSize: 14, marginBottom: 8 }}>暂无模板数据</div>
                <Text type="secondary">
                  点击右上角「运行分析」按钮自动挖掘高效果 Prompt 模板
                </Text>
              </div>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div>
      {/* Top info */}
      <Alert
        type="success"
        showIcon
        icon={<TrophyOutlined />}
        message={
          <span>
            🔍 分析完成：从 <b>{totalHits}</b> 条高效果 Prompt（点赞 ≥ <b>{threshold?.value}</b>）中挖掘到
            <b> {templates.length} </b> 个可复用模板
          </span>
        }
        style={{ marginBottom: 16 }}
      />

      {/* KPI cards */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <KpiCard title="模板数量" value={templates.length} />
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
            已挖掘的可复用爆款模板数
          </Text>
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="高效果 Prompt" value={totalHits} />
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
            符合点赞阈值的优质样本量
          </Text>
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="效果阈值" value={threshold?.value ?? '-'} />
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
            爆款判定标准（like_count）
          </Text>
        </Col>
        <Col xs={12} sm={6}>
          <KpiCard title="覆盖类别" value={coveredCategories.length} />
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4, padding: '0 16px' }}>
            模板覆盖的业务分类数
          </Text>
        </Col>
      </Row>

      {/* Charts row */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="模板效果 Top 5" bordered={false}>
            <EChartsWrapper option={top5Option} height={340} empty={!top5.length} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="模板覆盖类别分布" bordered={false}>
            <EChartsWrapper option={catDistOption} height={340} empty={!Object.keys(catCounts).length} />
          </Card>
        </Col>
      </Row>

      {/* Filter bar */}
      <Card bordered={false} style={{ marginBottom: 16 }}>
        <Row gutter={12} align="middle">
          <Col flex="auto">
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="搜索模板内容、类别、风格..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </Col>
          <Col>
            <Select
              allowClear
              placeholder="按类别筛选"
              style={{ width: 180 }}
              value={categoryFilter}
              onChange={setCategoryFilter}
              options={coveredCategories.map(c => ({ label: c, value: c }))}
            />
          </Col>
          <Col>
            <Select
              value={sortBy}
              onChange={setSortBy}
              style={{ width: 160 }}
              options={[
                { label: '按点赞排序', value: 'avg_likes' },
                { label: '按样本量排序', value: 'usage_count' },
                { label: '按评分排序', value: 'avg_score' },
              ]}
            />
          </Col>
          <Col>
            <Text type="secondary">共 {filteredTemplates.length} 个</Text>
          </Col>
        </Row>
      </Card>

      {/* Template grid + detail */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={selectedTemplate ? 14 : 24}>
          {filteredTemplates.length === 0 ? (
            <Card bordered={false}>
              <Empty description="没有匹配的模板，请调整筛选条件" />
            </Card>
          ) : (
            <Row gutter={[12, 12]}>
              {filteredTemplates.map(t => (
                <Col xs={24} sm={12} lg={selectedTemplate ? 12 : 8} key={t.id}>
                  <Card
                    hoverable
                    size="small"
                    onClick={() => setSelectedTemplate(t)}
                    style={{
                      border: selectedTemplate?.id === t.id ? '2px solid #1677ff' : '1px solid #f0f0f0',
                      height: '100%',
                    }}
                  >
                    <div style={{ marginBottom: 8 }}>
                      <Tag color="blue">{t.category}</Tag>
                      <Tag color="green">{t.style}</Tag>
                    </div>
                    <Paragraph ellipsis={{ rows: 3 }} style={{ fontSize: 13, marginBottom: 8, minHeight: 60 }}>
                      {t.template_prompt}
                    </Paragraph>
                    <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#999', justifyContent: 'space-between' }}>
                      <span><LikeOutlined /> {t.avg_likes}</span>
                      <span><StarOutlined /> {t.avg_score}</span>
                      <span>样本 {t.usage_count}</span>
                    </div>
                    <Button
                      size="small"
                      type="link"
                      icon={<CopyOutlined />}
                      onClick={e => { e.stopPropagation(); handleCopy(t.template_prompt); }}
                      style={{ padding: 0, marginTop: 8 }}
                    >
                      一键复制
                    </Button>
                  </Card>
                </Col>
              ))}
            </Row>
          )}
        </Col>

        {/* Detail panel */}
        {selectedTemplate && (
          <Col xs={24} lg={10}>
            <Card
              title={`模板详情 #${selectedTemplate.id + 1}`}
              bordered={false}
              extra={
                <Button
                  size="small"
                  type="primary"
                  icon={<CopyOutlined />}
                  onClick={() => handleCopy(selectedTemplate.template_prompt)}
                >
                  复制模板
                </Button>
              }
            >
              <div style={{ marginBottom: 16 }}>
                <Text type="secondary">类别 / 风格</Text>
                <div style={{ marginTop: 4 }}>
                  <Tag color="blue">{selectedTemplate.category}</Tag>
                  <Tag color="green">{selectedTemplate.style}</Tag>
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <Text type="secondary">模板结构</Text>
                <Paragraph code style={{ marginTop: 4 }}>
                  {selectedTemplate.pattern}
                </Paragraph>
              </div>

              <div style={{ marginBottom: 16 }}>
                <Text type="secondary">生成的模板 Prompt</Text>
                <Paragraph
                  style={{
                    background: '#f6ffed',
                    padding: 12,
                    borderRadius: 8,
                    border: '1px solid #b7eb8f',
                    marginTop: 4,
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {selectedTemplate.template_prompt}
                </Paragraph>
              </div>

              <div style={{ marginBottom: 16 }}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Text type="secondary">平均点赞</Text>
                    <div style={{ fontSize: 20, fontWeight: 700, color: '#52c41a' }}>{selectedTemplate.avg_likes}</div>
                  </Col>
                  <Col span={8}>
                    <Text type="secondary">平均收藏</Text>
                    <div style={{ fontSize: 20, fontWeight: 700, color: '#1677ff' }}>{selectedTemplate.avg_collects}</div>
                  </Col>
                  <Col span={8}>
                    <Text type="secondary">平均评分</Text>
                    <div style={{ fontSize: 20, fontWeight: 700, color: '#faad14' }}>{selectedTemplate.avg_score}</div>
                  </Col>
                </Row>
              </div>

              <div>
                <Text type="secondary">原始高效果 Prompt 示例</Text>
                <List
                  size="small"
                  dataSource={selectedTemplate.examples}
                  renderItem={(item, idx) => (
                    <List.Item>
                      <div>
                        <Tag color="blue">{idx + 1}</Tag>
                        <Paragraph ellipsis={{ rows: 2 }} style={{ fontSize: 12, margin: 0, display: 'inline' }}>
                          {item}
                        </Paragraph>
                      </div>
                    </List.Item>
                  )}
                />
              </div>
            </Card>
          </Col>
        )}
      </Row>
    </div>
  );
};

export default TemplateMarketPage;
