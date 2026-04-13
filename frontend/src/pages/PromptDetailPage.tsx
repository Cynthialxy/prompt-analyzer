import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Typography, Spin, Empty, Button, Tag, Row, Col } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { fetchPromptDetail } from '../api/endpoints';

const { Text, Paragraph } = Typography;

const PromptDetailPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['prompt-detail', projectId],
    queryFn: () => fetchPromptDetail(projectId!),
    enabled: !!projectId,
    retry: 0,
    staleTime: 5 * 60 * 1000,
  });

  if (!projectId) return <Empty description="缺少 project_id" />;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>
        返回
      </Button>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
      ) : isError || !data || data.error ? (
        <Card bordered={false}>
          <Empty description="未找到 Prompt 数据" />
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>Project ID：{projectId}</Text>
          </div>
        </Card>
      ) : (
        <Card bordered={false}>
          <Text type="secondary" style={{ fontSize: 12 }}>Prompt 内容</Text>
          <Paragraph style={{ fontSize: 15, marginTop: 8, background: '#f5f5f5', padding: 16, borderRadius: 8, whiteSpace: 'pre-wrap' }}>
            {data.prompt}
          </Paragraph>
          <Row gutter={[16, 8]} style={{ marginTop: 12 }}>
            {data.llm_category && <Col><Text type="secondary">类别：</Text><Tag color="blue">{data.llm_category}</Tag></Col>}
            {data.llm_style && <Col><Text type="secondary">风格：</Text><Tag color="green">{data.llm_style}</Tag></Col>}
            {data.like_count != null && <Col><Text type="secondary">点赞：</Text><Text>{data.like_count}</Text></Col>}
            {data.collect_count != null && <Col><Text type="secondary">收藏：</Text><Text>{data.collect_count}</Text></Col>}
            {data.score != null && <Col><Text type="secondary">评分：</Text><Text>{Number(data.score).toFixed(1)}</Text></Col>}
          </Row>
          <div style={{ marginTop: 12 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>Project ID：{projectId}</Text>
          </div>
        </Card>
      )}
    </div>
  );
};

export default PromptDetailPage;
