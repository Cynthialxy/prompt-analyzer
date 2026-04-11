import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Typography, Spin, Empty, Button } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useEffectAnalysis } from '../hooks/useAnalysisData';

const { Text, Paragraph } = Typography;

const PromptDetailPage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  // Try to find the prompt in the already-loaded effect analysis hit prompts cache
  const { data: effectData, isLoading } = useEffectAnalysis('like_count');

  if (!projectId) return <Empty description="缺少 project_id" />;

  const hitPrompt = effectData?.hit_prompts?.find(
    (p: { project_id: string }) => p.project_id === projectId
  );

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} type="text" onClick={() => navigate(-1)} style={{ marginBottom: 16 }}>
        返回
      </Button>

      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 100 }}><Spin size="large" /></div>
      ) : hitPrompt ? (
        <Card bordered={false}>
          <Text type="secondary" style={{ fontSize: 12 }}>Prompt 内容</Text>
          <Paragraph style={{ fontSize: 16, marginTop: 8, background: '#f5f5f5', padding: 16, borderRadius: 8 }}>
            {hitPrompt.prompt}
          </Paragraph>
          <Text type="secondary" style={{ fontSize: 12 }}>Project ID：{projectId}</Text>
        </Card>
      ) : (
        <Card bordered={false}>
          <Empty description="未找到 Prompt 数据" />
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>Project ID：{projectId}</Text>
          </div>
        </Card>
      )}
    </div>
  );
};

export default PromptDetailPage;
