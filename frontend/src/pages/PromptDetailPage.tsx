import React from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Row, Col, Card, Tag, Typography, Descriptions, Progress, List, Alert, Spin, Empty, Button } from 'antd';
import { ArrowLeftOutlined, CopyOutlined, LikeOutlined, StarOutlined, HeartOutlined } from '@ant-design/icons';
import EChartsWrapper from '../components/charts/EChartsWrapper';
import { usePromptAnalysis, useSimilarPrompts } from '../hooks/useAnalysisData';
import type { PromptAnalysis, SimilarPrompt } from '../types';

const { Text, Paragraph, Title } = Typography;

const INTENT_LABELS: Record<string, string> = {
  character_design: '角色设计', creature_animal: '生物动物', vehicle_transport: '交通工具',
  architecture_scene: '建筑场景', prop_item: '道具物品', weapon_armor: '武器装甲',
  furniture_decor: '家具装饰', food_nature: '食物自然', abstract_logo: '抽象标志', other: '其他',
};

const GRADE_COLORS: Record<string, string> = {
  A: '#52c41a', B: '#1677ff', C: '#faad14', D: '#fa8c16', F: '#ff4d4f', 'N/A': '#d9d9d9',
};

const DIM_LABELS: Record<string, string> = {
  specificity: '具体性', clarity: '清晰度', creativity: '创造力',
  technical_detail: '技术细节', actionability: '可执行性',
};

const PromptDetailPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: analysis, isLoading: analysisLoading } = usePromptAnalysis(projectId || '');
  const { data: similarData, isLoading: similarLoading } = useSimilarPrompts(projectId || '');

  if (!projectId) return <Empty description="缺少 project_id" />;

  const a = analysis as PromptAnalysis | undefined;
  const similars = (similarData?.results || []) as SimilarPrompt[];

  // Quality radar chart
  const dims = ['specificity', 'clarity', 'creativity', 'technical_detail', 'actionability'];
  const radarOption = a?.dimensions ? {
    radar: {
      indicator: dims.map(d => ({ name: DIM_LABELS[d] || d, max: 5 })),
    },
    series: [{
      type: 'radar',
      data: [{
        value: dims.map(d => a.dimensions[d] || 0),
        name: '质量评分',
        areaStyle: { opacity: 0.3 },
        itemStyle: { color: '#1677ff' },
      }],
    }],
  } : null;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>
        返回
      </Button>

      {analysisLoading ? (
        <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" tip="正在分析 Prompt..." /></div>
      ) : a?.error ? (
        <Alert type="error" message="分析失败" description={a.error} />
      ) : a ? (
        <>
          {/* Header: Prompt + KPIs */}
          <Card bordered={false} style={{ marginBottom: 16 }}>
            <Row gutter={24}>
              <Col flex="auto">
                <Text type="secondary" style={{ fontSize: 12 }}>Prompt 内容</Text>
                <Paragraph style={{ fontSize: 16, marginTop: 4, background: '#f5f5f5', padding: 16, borderRadius: 8 }}>
                  {a.prompt}
                </Paragraph>
                <div>
                  {a.intent && <Tag color="blue">{INTENT_LABELS[a.intent] || a.intent}</Tag>}
                  {a.sub_intent && <Tag color="cyan">{a.sub_intent}</Tag>}
                  {a.confidence > 0 && <Tag>置信度 {(a.confidence * 100).toFixed(0)}%</Tag>}
                </div>
              </Col>
              <Col style={{ minWidth: 120, textAlign: 'center' }}>
                <div style={{ marginBottom: 8 }}>
                  <Progress
                    type="circle"
                    percent={a.quality_score}
                    size={80}
                    strokeColor={GRADE_COLORS[a.grade] || '#1677ff'}
                    format={() => <span style={{ fontSize: 20, fontWeight: 700 }}>{a.grade}</span>}
                  />
                </div>
                <Text type="secondary">质量 {a.quality_score} 分</Text>
              </Col>
            </Row>
          </Card>

          {/* Analysis Panel */}
          <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
            {/* Left: Quality + Suggestions */}
            <Col xs={24} lg={14}>
              <Card title="质量维度分析" bordered={false} style={{ marginBottom: 16 }}>
                {radarOption ? (
                  <EChartsWrapper option={radarOption} height={280} />
                ) : (
                  <Empty description="暂无质量数据" />
                )}
              </Card>

              {a.optimization_suggestions?.length > 0 && (
                <Card title="优化建议" bordered={false} style={{ marginBottom: 16 }}>
                  <List
                    dataSource={a.optimization_suggestions}
                    renderItem={(item, idx) => (
                      <List.Item>
                        <Tag color="blue">{idx + 1}</Tag> {item}
                      </List.Item>
                    )}
                  />
                </Card>
              )}

              {a.optimized_prompt && (
                <Card
                  title="优化后的 Prompt"
                  bordered={false}
                  extra={
                    <Button
                      size="small"
                      icon={<CopyOutlined />}
                      onClick={() => navigator.clipboard.writeText(a.optimized_prompt)}
                    >
                      复制
                    </Button>
                  }
                >
                  <Paragraph style={{ background: '#f6ffed', padding: 12, borderRadius: 8, border: '1px solid #b7eb8f' }}>
                    {a.optimized_prompt}
                  </Paragraph>
                </Card>
              )}
            </Col>

            {/* Right: Similar Prompts */}
            <Col xs={24} lg={10}>
              <Card title={`相似 Prompt${similarLoading ? '（加载中...）' : ` (${similars.length})`}`} bordered={false}>
                {similarLoading ? (
                  <Spin />
                ) : similars.length > 0 ? (
                  <List
                    dataSource={similars}
                    renderItem={item => (
                      <List.Item
                        style={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/prompt/${item.project_id}`)}
                      >
                        <div style={{ width: '100%' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <Text ellipsis style={{ maxWidth: '70%', fontSize: 13 }}>{item.prompt}</Text>
                            <Tag color="blue">{(item.similarity_score * 100).toFixed(0)}%</Tag>
                          </div>
                          <div>
                            {item.llm_category && <Tag style={{ fontSize: 11 }}>{item.llm_category}</Tag>}
                            {item.like_count > 0 && <span style={{ fontSize: 11, color: '#999' }}><LikeOutlined /> {item.like_count}</span>}
                          </div>
                        </div>
                      </List.Item>
                    )}
                  />
                ) : (
                  <Empty description="暂无相似 Prompt（请先运行分析管线构建向量索引）" />
                )}
              </Card>
            </Col>
          </Row>

          {/* Metadata */}
          <Card title="元数据" bordered={false}>
            <Descriptions column={3} size="small">
              <Descriptions.Item label="Project ID">{projectId}</Descriptions.Item>
              <Descriptions.Item label="意图分类">{INTENT_LABELS[a.intent] || a.intent}</Descriptions.Item>
              <Descriptions.Item label="子意图">{a.sub_intent || '-'}</Descriptions.Item>
            </Descriptions>
          </Card>
        </>
      ) : (
        <Empty description="未找到 Prompt 数据" />
      )}
    </div>
  );
};

export default PromptDetailPage;
